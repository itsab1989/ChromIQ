"""A simulated ChromIQ helper for the table job's reading (test support, not shipped).

``HelperSim`` stands in for the helper PROCESS, not for the reader module: its ``proc_class()``
replaces ``reader._Proc`` while a ``reader.SpotReader`` is built, so the job's readings go
through the app's own ``SpotReader`` code (open, goto, read, finish, close) and every start is
recorded with its exact arguments. It speaks the helper's JSON events as
``native/chartread_helper`` emits them (instrument, cal_required, cal_done, spot_ready,
patch_read, unread_confirm, saved, error), on the table simulator's clock, and reads whatever
stands under the simulated sensor. Like ArgyllCMS (ENABLE_NONVCAL) a calibration made by one
reader is found by the next. It writes the row's .ti3 as chartread does when told "done".

Faults (``HelperSim(faults=...)``):
  open        no_instrument / busy / wrong_model / no_model / dies / silent / cal_fails /
              cal_other_cond, for every reader or only the reader number ``open_at``
  read        {n: kind}: the n-th reading of the whole sitting (1-based); kinds: error, coms,
              implausible, no_values, other_loc, dies, slow, cal_required
  read_loc    {loc: kind}: every reading of that patch (a patch that always fails)
  read_once   {loc: kind}: the first reading of that patch only
  read_s      seconds of the simulator's clock per reading (default 0.9)
The tester's own simulator objects (part C 0.6.0's CSimTable) work here unchanged.
"""
from __future__ import annotations

import collections
import json
import random
from pathlib import Path

WAVELENGTHS = list(range(380, 731, 10))


#: final fix round, S-1: the table's white tile under the opening while the arm is at rest
#: (Y below 300 units), as on the real table: 88 % in every band (the volunteer's table read
#: Y 89.78 there with a white made on the instrument's own tile)
REST_TILE = 0.88


def spectrum_at(x: float, y: float) -> "list[float]":
    """A smooth spectrum per 8.7 mm cell (0..1), the same rule as the strip simulator's; the
    table's white tile at rest."""
    if y < 300:
        return [REST_TILE] * 36
    cx, cy = round(x / 87.0), round(y / 87.0)
    r = random.Random(cx * 10007 + cy)
    base = [r.uniform(0.05, 0.9) for _ in range(4)]
    out = []
    for w in range(36):
        t = w / 35 * 3
        i = min(int(t), 2)
        f = t - i
        out.append(base[i] * (1 - f) + base[i + 1] * f)
    return out


def _read_ti2(path: Path) -> "list[tuple[str, str]]":
    out = []
    mode = None
    for ln in path.read_text(encoding="ascii").splitlines():
        s = ln.strip()
        if s == "BEGIN_DATA":
            mode = "d"
            continue
        if s == "END_DATA":
            mode = None
            continue
        if mode == "d" and s:
            parts = s.split()
            out.append((parts[0], parts[1].strip('"')))
    return out


class HelperSim:
    def __init__(self, sim, faults=None, reader_module=None):
        """*reader_module*: whose ``_Proc`` this helper stands in for and whose ReaderFailed it
        raises (the app's ``workflow.i1io.table.reader``; tester 0.6.0's ``i1io_reader`` for
        the wire capture)."""
        if reader_module is None:
            from workflow.i1io.table import reader as reader_module
        self.rd = reader_module
        self.sim = sim
        self.faults = dict(faults or {})
        self.started: "list[list[str]]" = []
        self.charts: "list[str]" = []
        self.calibrated = False
        self.calibrations = 0
        self.reads = 0
        self.readings_at: "list[tuple]" = []
        self.procs: "list[FakeHelperProc]" = []
        #: called with the sitting's reading count at every "read" (tests: a stop or a problem
        #: report while a reading is on its way)
        self.on_read = None
        self.failed_once: "set[str]" = set()
        #: round B: every button wait started (FakePressProc)
        self.press_procs: "list[FakePressProc]" = []
        #: round B: every table-scan reader started (folders), and the readers themselves
        self.scans: "list[str]" = []
        self.scan_readers: list = []
        self.strip_calibrated = False

    def proc_class(self):
        helper = self

        class _P(FakeHelperProc):
            pass
        _P.helper = helper
        return _P

    def press_factory(self, path: str = "/sim/bin/chromiq-chartread"):
        """Round B: a button-wait factory for the job: the app's own reader.PressWaiter with a
        simulated helper process (FakePressProc) behind it."""
        return _press_factory_for(self, path)

    def scan_factory(self):
        """Round B: a table-scan reader factory for the job: tester 0.6.0's own simulated
        table-scan helper (part_c_sim.FakeScanReader, the strip scan at the recorded pace on the
        table simulator's clock). Like ArgyllCMS, a strip white made by one reader is found by
        the next. Faults: ``HelperSim(faults={"scan": {...}})`` (FakeScanReader's own: no_lamp,
        not_ready, lights_err, dark_fail, fire_unsent, dies_at_fire, cal_fails, no_instrument,
        dead), ``"scan_at": n`` for the n-th scan reader only."""
        from tests.i1io_table import part_c_sim as csim
        helper = self

        def make(folder, log):
            helper.scans.append(str(folder))
            faults = dict(helper.faults.get("scan") or {})
            at = helper.faults.get("scan_at")
            if at is not None and at != len(helper.scans):
                faults = {}
            if helper.strip_calibrated:
                faults["restored"] = True
            r = _ChartScanReader(helper.sim, str(folder), log, faults)
            r.colour_at = helper.colour_at
            real_cal = r.calibrate

            def calibrate(place, timeout=120.0):
                real_cal(place, timeout)
                helper.strip_calibrated = True
            r.calibrate = calibrate
            helper.scan_readers.append(r)
            return r
        return make

    def colour_at(self, x: float, y: float) -> "list[float]":
        """What the strip reader sees at table point (x, y): the printed sheet, as the spot
        reader sees it at a patch's centre (spectrum_at of the nearest patch centre of the job's
        aligned sheet, within half a patch), paper white elsewhere. Without a job: the strip
        simulator's own cells."""
        job = getattr(self, "job", None)
        if job is None or job.alignment is None:
            from tests.i1io_table import part_c_sim as csim
            return csim._spectrum_at(x, y)
        cache = getattr(self, "_centres", None)
        if cache is None or cache[0] is not job.alignment:
            from workflow.i1io.table import scan as sc
            pts = []
            for st in job.sheet["pages"][job.page]["strips"]:
                for q in st["patches"]:
                    u = sc.sheet_table_mm(job.sheet, q["centre_mm"])
                    try:
                        pts.append(job.alignment.target(u, "patch", run_out_mm=0.5,
                                                        front_y=10 ** 6))
                    except Exception:      # noqa: BLE001 - off the area: not printed here
                        continue
            half = 10.0 * float(job.sheet["patch_mm"][1]) / 2.0
            self._centres = cache = (job.alignment, pts, half)
        _al, pts, half = cache
        best = None
        for c in pts:
            dd = max(abs(c[0] - x), abs(c[1] - y))
            if dd <= half and (best is None or dd < best[0]):
                best = (dd, c)
        if best is None:
            return [0.88] * 36
        return spectrum_at(*best[1])

    def press(self) -> "dict | None":
        """The person presses the instrument's button (the newest button wait hears it)."""
        live = [p for p in self.press_procs if p.alive()]
        return live[-1].press() if live else None

    def factory(self, path: str = "/sim/bin/chromiq-chartread"):
        """A reader factory for the job: the app's own reader.SpotReader with this simulated
        helper process behind it."""
        rd = self.rd

        def make(folder, name, patches, calibrate, extra_args, log):
            orig = rd._Proc
            rd._Proc = self.proc_class()
            try:
                return rd.SpotReader(Path(path), folder, name, patches, log, calibrate,
                                     extra_args=tuple(extra_args))
            finally:
                rd._Proc = orig
        return make


def _chart_scan_reader():
    from tests.i1io_table import part_c_sim as csim

    class ChartScanReader(csim.FakeScanReader):
        """part_c_sim's table-scan reader, reading the job's printed sheet (HelperSim.colour_at)
        instead of the strip simulator's own cells; everything else (timing, lamp, faults) is
        the tester's simulator unchanged."""
        colour_at = None

        def _stream(self, name, n, p):
            orig = csim._spectrum_at
            if self.colour_at is not None:
                csim._spectrum_at = self.colour_at
            try:
                return super()._stream(name, n, p)
            finally:
                csim._spectrum_at = orig
    return ChartScanReader


def _ChartScanReader(*a, **k):
    return _chart_scan_reader()(*a, **k)


def _press_factory_for(helper: "HelperSim", path: str):
    rd = helper.rd

    class _P(FakePressProc):
        pass
    _P.helper = helper

    def make(folder, log):
        orig = rd._Proc
        rd._Proc = _P
        try:
            return rd.PressWaiter(Path(path), folder, log)
        finally:
            rd._Proc = orig
    return make


class FakePressProc:
    """The helper's button wait (``--i1io-press-wait``, round B), simulated with the native
    mode's rules (chromiq_presswait.c): a press is reported only while armed and not sooner
    than min_ms after the arm (the simulator's clock), once per arm; disarm, quit. The
    person's thumb is :meth:`press`. Faults (``HelperSim(faults={"press": ...})``):
    ``no_instrument`` / ``wrong_model`` / ``dies`` at the start, ``dies_on_arm``."""
    helper: "HelperSim" = None

    def __init__(self, argv, log, cwd):
        h = self.helper
        self.argv = list(argv)
        self.log = log
        self.events: "list[dict]" = []
        self.q: "collections.deque[dict]" = collections.deque()
        self._alive = True
        self.armed: "str | None" = None
        self.t_arm = 0.0
        self.min_s = 0.4
        self.wait_s = 600.0
        self.sent: "list[dict]" = []
        h.started.append(list(argv))
        h.press_procs.append(self)
        log("INST", "start (simulated helper): " + " ".join(Path(a).name if i == 0 else a
                                                             for i, a in enumerate(argv)))
        fault = h.faults.get("press")
        self._emit({"event": "press_wait_start", "t": 0, "build": "sim +i1io-press-wait"})
        if fault == "dies":
            self._die()
            return
        if fault == "no_instrument":
            self._emit({"event": "error", "kind": "no_instrument", "detail": ""})
            self._die()
            return
        if fault == "wrong_model":
            self._emit({"event": "error", "kind": "press_instrument", "detail": "not an i1Pro 2"})
            self._die()
            return
        self._emit({"event": "press_wait_ready", "t": 0, "model": "X-Rite i1 Pro 2"})

    def _now(self) -> float:
        return float(self.helper.sim.clock)

    def _emit(self, ev: dict) -> None:
        self.events.append(ev)
        self.q.append(ev)
        self.log("INST", json.dumps(ev))

    def _die(self) -> None:
        self._alive = False
        self.q.append({"event": "helper_gone"})

    def press(self) -> "dict | None":
        """The person presses the instrument's button once."""
        if not self._alive:
            return None
        if self.armed is not None and self._now() - self.t_arm >= self.wait_s:
            self._emit({"event": "press_timeout", "id": self.armed})
            self.armed = None
        if self.armed is None:
            ev = {"event": "press_ignored", "why": "not_armed"}
        elif self._now() - self.t_arm < self.min_s:
            ev = {"event": "press_ignored", "why": "too_soon", "id": self.armed}
        else:
            ev = {"event": "press", "id": self.armed,
                  "after_ms": int(1000 * (self._now() - self.t_arm))}
            self.armed = None
        self._emit(ev)
        return ev

    def send(self, obj) -> None:
        ReaderFailed = self.helper.rd.ReaderFailed
        self.sent.append(dict(obj))
        self.log("INST", "cmd " + json.dumps(obj))
        if not self._alive:
            raise ReaderFailed("the reader stopped listening (BrokenPipeError)")
        cmd = obj.get("cmd")
        if cmd == "press_arm":
            if self.helper.faults.get("press") == "dies_on_arm":
                self._die()
                return
            self.armed = str(obj.get("id"))
            self.t_arm = self._now()
            self.min_s = int(obj.get("min_ms", 400)) / 1000.0
            self.wait_s = int(obj.get("wait_ms", 600000)) / 1000.0
            self._emit({"event": "press_armed", "id": self.armed})
        elif cmd == "press_disarm":
            self._emit({"event": "press_disarmed", "id": self.armed or "",
                        "was_armed": self.armed is not None})
            self.armed = None
        elif cmd in ("press_quit", "quit"):
            self._emit({"event": "press_wait_end"})
            self._alive = False
            self.q.append({"event": "helper_gone"})
        else:
            self._emit({"event": "press_unknown"})

    def alive(self) -> bool:
        return self._alive

    def wait(self, names, timeout: float):
        while self.q:
            ev = self.q.popleft()
            if ev.get("event") in names or ev.get("event") in ("helper_gone", "error"):
                return ev
        return None

    def poll(self, name):
        while self.q:
            ev = self.q.popleft()
            if ev.get("event") in (name, "helper_gone"):
                return ev
        return None

    def stop(self, quit_cmd) -> None:
        if self._alive:
            try:
                self.send(quit_cmd)
            except Exception:      # noqa: BLE001
                pass
        self._alive = False


class FakeHelperProc:
    helper: HelperSim = None

    def __init__(self, argv, log, cwd):
        h = self.helper
        self.argv = list(argv)
        self.log = log
        self.cwd = Path(cwd)
        self.events: "list[dict]" = []
        self.q: "collections.deque[dict]" = collections.deque()
        self._alive = True
        self.index = len(h.started) + 1
        h.started.append(list(argv))
        h.procs.append(self)
        self.name = argv[argv.index("-p") + 1]
        ti2 = self.cwd / f"{self.name}.ti2"
        h.charts.append(ti2.read_text(encoding="ascii"))
        self.patches = _read_ti2(ti2)
        self.no_cal = "-N" in argv
        self.no_spectral = "-n" in argv
        self.lab_only = "-l" in argv
        self.lab_too = "-L" in argv
        self.read: "dict[str, list]" = {}
        self.at = 0
        self.state = "open"
        log("INST", "start (simulated helper): " + " ".join(Path(a).name if i == 0 else a
                                                             for i, a in enumerate(argv)))
        fault = h.faults.get("open")
        if fault and h.faults.get("open_at") not in (None, self.index):
            fault = None
        self._start(fault)

    # ---- the helper's side -----------------------------------------------------------------
    def _emit(self, ev: dict) -> None:
        self.events.append(ev)
        self.q.append(ev)
        self.log("INST", json.dumps(ev))

    def _die(self) -> None:
        self._alive = False
        self.q.append({"event": "helper_gone"})

    def _start(self, fault) -> None:
        h = self.helper
        if fault == "dies":
            self._die()
            return
        if fault == "silent":
            return
        if fault in ("no_instrument", "busy"):
            self._emit({"event": "error", "kind": "no_instrument",
                        "detail": "Instrument is busy (in use by another program)"
                        if fault == "busy" else ""})
            self._die()
            return
        if fault != "no_model":
            self._emit({"event": "instrument", "model": "X-Rite i1 Pro" if fault ==
                        "wrong_model" else "X-Rite i1 Pro 2", "chart_model": "X-Rite i1 Pro 2"})
        self._cal_fault = fault
        if not self.no_cal or not h.calibrated:
            self.state = "cal"
            self._emit({"event": "cal_required", "cond": "man_trans_white" if fault ==
                        "cal_other_cond" else "man_ref_white", "id": "", "optional": False})
            return
        self._ready()

    def _ready(self) -> None:
        self.state = "ready"
        if self.at < len(self.patches):
            sid, loc = self.patches[self.at]
            self._emit({"event": "spot_ready", "id": sid, "loc": loc, "read": False,
                        "all_done": False, "exyz": [50.0, 50.0, 50.0]})

    def _fault_for(self, loc: str) -> "str | None":
        h = self.helper
        by_loc = h.faults.get("read_loc", {})
        if loc in by_loc:
            return by_loc[loc]
        once = h.faults.get("read_once", {})
        if loc in once and loc not in h.failed_once:
            h.failed_once.add(loc)
            return once[loc]
        return h.faults.get("read", {}).get(h.reads)

    def _xyz_here(self):
        x, y = self.helper.sim.pos
        spec = spectrum_at(x, y)
        Y = 100 * sum(spec) / len(spec)
        return [round(Y * 0.96, 4), round(Y, 4), round(Y * 0.82, 4)], [100 * v for v in spec]

    def send(self, obj) -> None:
        ReaderFailed = self.helper.rd.ReaderFailed
        h, sim = self.helper, self.helper.sim
        self.log("INST", "cmd " + json.dumps(obj))
        if not self._alive:
            raise ReaderFailed("the reader stopped listening (BrokenPipeError)")
        cmd = obj.get("cmd")
        if cmd == "ok" and self.state == "cal":
            sim.clock += 3.0
            # the events of the REAL helper for the calibration a session starts with
            # (chromiq_cal.c: "cal_done"; a failure is an "error" of kind "cal_failed").
            # Until 4.3.46 this simulator sent "cal_result", the event of a calibration the
            # person asks for, and so hid that the reader never saw a white on a real i1Pro 2.
            if self._cal_fault == "cal_fails":
                self._emit({"event": "error", "kind": "cal_failed",
                            "detail": "simulated calibration failure"})
                return
            h.calibrated = True
            h.calibrations += 1
            self._emit({"event": "cal_done"})
            self._ready()
        elif cmd == "goto":
            loc = obj.get("patch")
            locs = [loc_ for _s, loc_ in self.patches]
            if loc not in locs:
                self._emit({"event": "error", "kind": "patch_not_found", "detail": loc})
                return
            self.at = locs.index(loc)
            self._ready()
        elif cmd == "read":
            h.reads += 1
            if h.on_read is not None:
                h.on_read(h.reads)
            sid, loc = self.patches[self.at]
            if sim.moving or sim.m2_pending is not None:
                sim.violations.append(f"a spot reading of {loc} while the arm moves")
            fault = self._fault_for(loc)
            if fault in ("error", "coms"):
                self._emit({"event": "error", "kind": "read_error" if fault == "error"
                            else "coms", "detail": ""})
                return
            if fault == "dies":
                self._die()
                return
            if fault == "slow":
                return
            if fault == "cal_required":
                self._emit({"event": "cal_required", "cond": "man_ref_white", "id": "",
                            "optional": False})
                return
            sim.clock += float(h.faults.get("read_s", 0.9))
            xyz, spec = self._xyz_here()
            h.readings_at.append((tuple(sim.pos), loc))
            if fault == "implausible":
                xyz, spec = [0.01, 0.01, 0.01], [0.01] * 36
            if fault == "no_values":
                self.read[loc] = [sid, xyz, spec]
                self._emit({"event": "patch_read", "id": sid, "loc": loc, "xyz": [],
                            "exyz": [], "de": 0})
                self.at = min(self.at + 1, len(self.patches) - 1)
                self._ready()
                return
            if fault == "other_loc":
                other = self.patches[(self.at + 1) % len(self.patches)]
                self._emit({"event": "patch_read", "id": other[0], "loc": other[1],
                            "xyz": xyz, "exyz": xyz, "de": 0.0})
                return
            self.read[loc] = [sid, xyz, spec]
            self._emit({"event": "patch_read", "id": sid, "loc": loc, "xyz": xyz,
                        "exyz": [50.0, 50.0, 50.0], "de": 1.0})
            # NOT simulated: the real helper also autosaves the .ti3 after every spot reading
            # ({"event":"saved"}; test_engine_spot.py::test_each_patch_read_autosaves). Several
            # tests here assume a row's earlier readings are lost when its reader dies (review
            # of 4.3.46, REVIEW.md); the app's assembly takes them either way.
            if self.at + 1 < len(self.patches):
                self.at += 1
            self._ready()
        elif cmd == "done":
            if len(self.read) < len(self.patches):
                self._emit({"event": "unread_confirm", "unread": len(self.patches)
                            - len(self.read)})
                self.state = "confirm"
                return
            self._save()
        elif cmd == "yes" and self.state == "confirm":
            self._save()
        elif cmd == "quit":
            self._alive = False

    def _save(self) -> None:
        """The real helper's end ("done"): chartread writes the .ti3, says {"event":"done"} and
        ends (chromiq_chartread.c, after read_strips; it sends no "saved" there: that is the
        autosave's word). Until 4.3.46 this simulator answered "saved" and stayed alive."""
        self._write(event=False)
        self._emit({"event": "done"})
        self._die()

    def _write(self, event: bool = True) -> None:
        path = self.cwd / f"{self.name}.ti3"
        if self.read:
            fields = ["SAMPLE_ID", "SAMPLE_LOC", "RGB_R", "RGB_G", "RGB_B"]
            if not self.lab_only:
                fields += ["XYZ_X", "XYZ_Y", "XYZ_Z"]
            if self.lab_only or self.lab_too:
                fields += ["LAB_L", "LAB_A", "LAB_B"]
            if not self.no_spectral:
                fields += [f"SPEC_{w}" for w in WAVELENGTHS]
            lines = ["CTI3   ", "", 'DESCRIPTOR "Argyll Calibration Target chart information 3"',
                     'ORIGINATOR "Argyll chartread"', 'CREATED "simulated"',
                     'DEVICE_CLASS "OUTPUT"', 'COLOR_REP "RGB_XYZ"',
                     'TARGET_INSTRUMENT "X-Rite i1 Pro 2"']
            if not self.no_spectral:
                lines += ['SPECTRAL_BANDS "36"', 'SPECTRAL_START_NM "380.000000"',
                          'SPECTRAL_END_NM "730.000000"']
            lines += ["", f"NUMBER_OF_FIELDS {len(fields)}", "BEGIN_DATA_FORMAT",
                      " ".join(fields) + " ", "END_DATA_FORMAT", "",
                      f"NUMBER_OF_SETS {len(self.read)}", "BEGIN_DATA"]
            for sid, loc in self.patches:
                if loc not in self.read:
                    continue
                _sid, xyz, spec = self.read[loc]
                row = [sid, f'"{loc}"', "50.00000", "50.00000", "50.00000"]
                if not self.lab_only:
                    row += [f"{v:.6f}" for v in xyz]
                if self.lab_only or self.lab_too:
                    row += [f"{xyz[1]:.6f}", "0.000000", "0.000000"]
                if not self.no_spectral:
                    row += [f"{v:.6f}" for v in spec]
                lines.append(" ".join(row))
            lines += ["END_DATA", ""]
            path.write_text("\n".join(lines), encoding="ascii")
        if event:
            self._emit({"event": "saved", "path": str(path), "read_patches": len(self.read)})

    # ---- reader._Proc's interface --------------------------------------------------------------
    def alive(self) -> bool:
        return self._alive

    def wait(self, names, timeout: float):
        while self.q:
            ev = self.q.popleft()
            if ev.get("event") in names or ev.get("event") in ("helper_gone", "error"):
                return ev
        self.helper.sim.clock += float(timeout)        # the wait ran out on the sim's clock
        return None

    def poll(self, name):
        while self.q:
            ev = self.q.popleft()
            if ev.get("event") in (name, "helper_gone"):
                return ev
        return None

    def stop(self, quit_cmd) -> None:
        if self._alive:
            try:
                self.send(quit_cmd)
            except Exception:      # noqa: BLE001
                pass
        self._alive = False


# ---- the run, its chart, the job -------------------------------------------------------------

def chart_ti2_text(sheet: dict) -> str:
    """A chart file for the sheet (every patch of every page by its sample id and location,
    device values made up from the id), as the run's ``.ti2`` is for an i1iO chart."""
    rows = sorted(((int(q["sample_id"]), q["loc"]) for pg in sheet["pages"]
                   for st in pg["strips"] for q in st["patches"]))
    out = ["CTI2   ", "", 'DESCRIPTOR "Argyll Calibration Target chart information 2"',
           'ORIGINATOR "simulated"', 'TARGET_INSTRUMENT "X-Rite i1 Pro 2"', 'COLOR_REP "RGB"',
           "", "NUMBER_OF_FIELDS 8", "BEGIN_DATA_FORMAT",
           "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z ", "END_DATA_FORMAT", "",
           f"NUMBER_OF_SETS {len(rows)}", "BEGIN_DATA"]
    for sid, loc in rows:
        r, g, b = (sid * 37) % 101, (sid * 53) % 101, (sid * 71) % 101
        out.append(f'{sid} "{loc}" {r:.5f} {g:.5f} {b:.5f} 50.00000 50.00000 50.00000 ')
    out += ["END_DATA", ""]
    return "\n".join(out)


STAMP = "20261117-140000"


def make_run(tmp_path: Path, sheet: dict, name: str = "Table-Target"):
    from core.file_manager import Run
    run = Run.for_dir(Path(tmp_path) / name / "runs" / "run1")
    run.dir.mkdir(parents=True, exist_ok=True)
    run.chart_ti2.write_text(chart_ti2_text(sheet), encoding="ascii")
    return run


def make_reading_job(tmp_path, sheet=None, aims=None, faults=None, run=True, stamp=STAMP,
                     instrument=None, helper_check=None, ask_after_each_step=True, sim=None,
                     app_marker_place=None, press=False, latency_guard=None, **simkw):
    """A table job with the simulated table AND the simulated helper behind the app's reader.
    *press*: round B's button wait is offered (the simulated helper's FakePressProc).
    Returns (job, sim, helper, run)."""
    from tests.i1io_table import job_harness as H
    from tests.i1io_table import part_c_sim as csim
    from tests.i1io_table import session_sim as ss
    from workflow.i1io.table import job as J
    from workflow.i1io.table import usb_system as us
    sheet = sheet or H.demo_sheet()
    if sim is None:
        sim = csim.CSimTable(part_c=True, aims=list(aims or H.demo_aims(sheet)), **simkw)
    helper = HelperSim(sim, faults)
    if run is True:
        r = make_run(tmp_path, sheet)
    elif run:
        r = run                              # a real project's Run (step 8 tests)
        if not r.chart_ti2.exists():
            r.dir.mkdir(parents=True, exist_ok=True)
            r.chart_ti2.write_text(chart_ti2_text(sheet), encoding="ascii")
    else:
        r = None
    transport = ss.SimTransport(sim)
    job = J.TableJob(sheet, run=r, stamp=stamp if r is not None else None,
                     folder=None if r is not None else Path(tmp_path) / "session",
                     open_transport=lambda: transport,
                     preflight=lambda: H.OK_PREFLIGHT, other_program=lambda: False,
                     ask_after_each_step=ask_after_each_step,
                     reader_factory=helper.factory(),
                     helper_check=helper_check or (lambda: None),
                     instrument_check=instrument or (lambda: us.Check("ok",
                                                                      {"i1pro_devices": 1})),
                     app_marker_place=app_marker_place,
                     press_factory=helper.press_factory() if press else None,
                     scan_factory=helper.scan_factory(), latency_guard=latency_guard)
    helper.job = job
    return job, sim, helper, r

