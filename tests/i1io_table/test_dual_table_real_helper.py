"""The i1Pro 2 dual scan on the table, patch by patch, against the REAL helper (2026-11-19).

The table's patch-by-patch reader is the app's ``rd.SpotReader`` started with the dual
arguments the job gives it (``DualSetup.spot_args``: the hand dual scan's own, the table's
white, ``--dual-table``, the row folder's conditions). 4.3.46 taught that reader the real
helper's own ways (``cal_done`` counts as the white, Esc out of its prompts, "retry" after a
failed reading, and NEVER a key at a calibration the instrument asks for in the middle of a
row: any key there starts the calibration on whatever lies under the arm).

With the dual scan that last rule matters twice: on a real i1Pro 2 a calibration made there
would be followed by the dual hook (``chromiq_dualdev.c`` ``cq_dd_after_cal``), which reads
the "tile" with the UV light over the PAPER and, with ``--dual-table``, keeps that reading for
every later row (``i1pro2_cq_dual_tile_save``). These tests run the committed helper with its
replay instrument in a dual session (an invented instrument, no real data) and hold the
reader to: no key after the request, no ``cal_done`` and no ``dual_calibration`` after it,
the helper ends by itself, the readings made before it are kept.

The replay instrument takes the dual scan's step-1 path (its LAMP / UV lines), not the device
path with the hook, so a second test pins the reader against the device path's own event
order (``dual_pass_result`` before the request), as the C sources emit it.
"""
from __future__ import annotations

import json
import queue
from pathlib import Path

import numpy as np
import pytest

from tests.i1io_table.test_4346_the_reader_hears_the_real_helper import (
    _helper_events, _real_helper)
from workflow.dual_scan import model
from workflow.dual_scan.scale import ScaleChoice
from workflow.dual_scan import storage as S
from workflow.i1io.table import dual_rows as dl
from workflow.i1io.table import reader as rd

pytestmark = pytest.mark.timeout(120)

WL = model.WAVELENGTHS
KEYS = ({"cmd": "ok"}, {"cmd": "done"}, {"cmd": "retry"}, {"cmd": "read"}, {"cmd": "yes"},
        {"cmd": "accept"})


def _vec(v):
    return " ".join(f"{x:.10g}" for x in v)


def _script(path: Path, patches: int) -> None:
    """An invented dual instrument (the engine test's shapes): DUALCAL, one strip of
    *patches* with XYZ, LAMP and UV lines."""
    band = (WL >= 410) & (WL <= 550)
    x = (WL - 410) / 140.0
    kA = np.where(band, 1.2e-4 * (1.0 + 0.8 * np.sin(np.pi * x)), 0.0)
    kD = np.where(band, kA * (1.6 + 0.9 * x), 0.0)
    W = 0.9 + 0.02 * np.cos(WL / 50.0)
    T = 0.012 * np.exp(-(WL - 380) / 25.0) + 1e-4
    E = 2.4e4 * (1.0 + 0.3 * (WL - 380) / 350.0)
    tab = model.UVTables.from_values(kA[:18], kD[:18])
    cal = model.DualCalibration(W, T, E, 139, 139)
    m2 = np.clip(np.linspace(0.3, 0.8, patches)[:, None] * np.ones((patches, 36)), 0.01, 0.97)
    g = m2.mean(axis=1, keepdims=True) * 900.0 * np.exp(-0.5 * ((WL - 440) / 25.0) ** 2)
    L, U, _m1 = model.forward(m2, g, cal, tab, 1.137)
    with path.open("w", encoding="utf-8") as fp:
        fp.write(f"PATCHES {patches}\nDUALCAL\nW {_vec(W)}\nT {_vec(T)}\nE {_vec(E)}\n"
                 f"KA {_vec(tab.kA[:18])}\nKD {_vec(tab.kD[:18])}\nCLOCKS 139 139\nSTRIP A\n")
        for i in range(patches):
            fp.write("50 50 50\n")
        for i in range(patches):
            fp.write(f"LAMP {_vec(L[i])}\nUV {_vec(U[i])}\n")


def _dual_reader(tmp_path, monkeypatch, patches=3):
    helper = _real_helper()
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    monkeypatch.setenv("CHROMIQ_ENGINE_MUTE", "1")
    monkeypatch.setenv("CHROMIQ_REPLAY_NEEDCAL", "1")
    replay = tmp_path / "replay.txt"
    _script(replay, patches)
    ch = ScaleChoice.standard()
    setup = dl.DualSetup(tuple(S.helper_args(ch, "table", "M2")), ch.value, ch.source, "M2",
                         "table")
    folder = tmp_path / "row"
    args = ("--replay", str(replay), "-S",
            *setup.spot_args(str(folder / "conditions"), dl.white_for_place("table")))
    lines: "list" = []
    r = rd.SpotReader(helper, folder, "row", [(str(i + 1), f"A{i + 1}")
                                             for i in range(patches)],
                      lambda k, m: lines.append((k, m)), False, extra_args=args)
    r._log_lines = lines
    return r


def _sent(r) -> "list[dict]":
    return [json.loads(m[4:]) for _k, m in r._log_lines if m.startswith("cmd ")]


def _names(r) -> "list[str]":
    return [e.get("event") for e in r.proc.events]


def test_a_calibration_asked_for_in_a_dual_row_is_never_answered(tmp_path, monkeypatch):
    r = _dual_reader(tmp_path, monkeypatch)
    r.open(lambda ev: True, timeout=20)
    names = _names(r)
    assert "conditions" in names, names
    cond = [e for e in r.proc.events if e.get("event") == "conditions"][-1]
    assert cond.get("active") is True, cond          # a dual session, not a plain one
    a1 = r.read("A1", timeout=10)
    assert len(a1.xyz) == 3
    n_sent = len(_sent(r))
    r.proc.send({"cmd": "swipe", "fault": "needs_cal"})   # the replay's next answer
    with pytest.raises(rd.ReaderFailed):
        r.read("A2", timeout=10)
    names = _names(r)
    i = names.index("cal_required")
    after = _sent(r)[n_sent:]
    ti3 = r.finish(timeout=10)
    names = _names(r)
    sent_after = _sent(r)[n_sent:]
    # after the request: no key at all, only Esc ("quit") on the way out
    keys = [c for c in sent_after[len(after):] if c in KEYS]
    assert keys == [], sent_after
    assert "cal_done" not in names[i:], names
    assert "dual_calibration" not in names[i:], names
    assert not r.proc.alive() and r.proc.p.returncode == 0
    # the reading made before the request is kept in the reader's own .ti3
    assert ti3 is not None and sorted(rd.read_ti3_spectra(ti3)[1]) == ["A1"]


def test_retry_is_never_sent_at_a_calibration_request_in_a_dual_row(tmp_path, monkeypatch):
    r = _dual_reader(tmp_path, monkeypatch)
    try:
        r.open(lambda ev: True, timeout=20)
        r.read("A1", timeout=10)
        r.proc.send({"cmd": "swipe", "fault": "needs_cal"})
        with pytest.raises(rd.ReaderFailed):
            r.read("A2", timeout=10)
        r.ready_loc = None                          # job._patch's second try
        with pytest.raises(rd.ReaderFailed):
            r.read("A2", timeout=5)
        assert {"cmd": "retry"} not in _sent(r)
        assert "cal_done" not in _names(r)[_names(r).index("cal_required"):]
    finally:
        r.close()
    assert not r.proc.alive()


# ---- the device path's own order (chromiq_dualdev.c, chromiq_chartread.c's spot loop) -------

class _Scripted:
    script: "list[dict]" = []

    def __init__(self, argv, log, cwd):
        self.sent: "list[dict]" = []
        self.q: "queue.Queue[dict]" = queue.Queue()
        self.events: "list[dict]" = []
        self._alive = True
        for ev in self.script:
            self.q.put(ev)

    def send(self, obj):
        self.sent.append(obj)
        if obj.get("cmd") == "quit":
            self._alive = False

    def alive(self):
        return self._alive

    def wait(self, names, timeout):
        while True:
            try:
                ev = self.q.get_nowait()
            except queue.Empty:
                return None
            self.events.append(ev)
            if ev.get("event") in names or ev.get("event") in ("helper_gone", "error"):
                return ev

    def poll(self, name):
        return None

    def stop(self, *a, **k):
        self._alive = False


#: a real i1Pro 2 in a dual session, patch by patch: a good patch (the UV half's
#: dual_pass_result, then patch_read, the autosave, the next patch), then the instrument asks
#: for a white in the middle of the row (cq_dd_spot returns early: no dual event for it)
DEVICE_ORDER = [
    {"event": "dual_calibration", "ok": True, "why": "", "mode": "spot", "lamp_clocks": 515,
     "uv_clocks": 515, "volts": [-1, -1], "driver": 0},
    {"event": "spot_ready", "id": "1", "loc": "A1", "read": False, "all_done": False},
    {"event": "dual_pass_result", "what": "spot", "strip": "", "ok": True, "why": "",
     "uv_readings": 1, "fewest_per_patch": -1, "uv_triggers": 1, "volts": [661, 657],
     "pairing": ""},
    {"event": "patch_read", "id": "1", "loc": "A1", "xyz": [40.0, 41.0, 35.0]},
    {"event": "saved", "path": "row.ti3", "read_patches": 1},
    {"event": "spot_ready", "id": "2", "loc": "A2", "read": False, "all_done": False},
    {"event": "cal_required", "cond": "man_ref_white", "id": "", "optional": False},
]


def test_the_device_paths_dual_events_never_hide_a_calibration_request(tmp_path, monkeypatch):
    assert {e["event"] for e in DEVICE_ORDER} <= _helper_events()
    proc = type("P", (_Scripted,), {"script": list(DEVICE_ORDER)})
    monkeypatch.setattr(rd, "_Proc", proc)
    r = rd.SpotReader(Path("chromiq-chartread"), tmp_path, "row", [("1", "A1"), ("2", "A2")],
                      lambda *a: None, False)
    r.open(lambda ev: True, timeout=1)
    r.read("A1", timeout=1)
    with pytest.raises(rd.ReaderFailed):
        r.read("A2", timeout=1)
    assert r._prompt()["event"] == "cal_required"
    r.finish(timeout=1)
    # read A1, read A2 (answered by the request), then nothing but Esc
    assert r.proc.sent[:2] == [{"cmd": "read"}, {"cmd": "read"}], r.proc.sent
    after = r.proc.sent[2:]
    assert after and all(c == {"cmd": "quit"} for c in after), r.proc.sent
