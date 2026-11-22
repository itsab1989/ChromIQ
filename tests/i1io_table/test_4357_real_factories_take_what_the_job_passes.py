"""4.3.57 (item 34): the REAL reader factories take every argument the job passes them.

The table owner's two dual scan tries of 22 Nov 2026 (rows as strips) stopped right after the
dual calibration with "an unexpected error (TypeError)": the job builds the strip white's
reader with ``self._scan_factory(folder, log, extra_args=...)``, and the real default
``_default_scan_reader(folder, log)`` took no ``extra_args``. The simulated factory every test
injected (``reader_sim.HelperSim.scan_factory``) did take it, so the suite never saw that the
dual scan with rows had never been able to start on a real table (since 4.3.48).

Three guards here, each of which would have caught it:

1. the strip white built through the REAL default factory, the real ``reader.ScanReader`` and
   the real ``reader._Proc`` subprocess, against a FAKE HELPER EXECUTABLE that speaks the
   table-scan protocol (nothing is simulated inside the app's own code), with and without the
   dual scan;
2. every call the job makes to an injectable (``self._scan_factory(...)`` and the others,
   found in job.py's source) binds to the real default's signature, and the window's calls of
   ``JOB_FACTORY`` bind to ``default_job_factory``;
3. every simulated factory / reader / process / transport of tests/i1io_table has the same
   signature as its real counterpart, and a method only the simulation has is never called
   by the app.
"""
from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import part_c_sim as csim
from tests.i1io_table import reader_sim as RS
from tests.i1io_table import session_sim as ss
from workflow.i1io.table import dual_rows as dl
from workflow.i1io.table import job as J
from workflow.i1io.table import reader as rd
from workflow.i1io.table import session_table as st
from workflow.i1io.table import usb_system as us

ROOT = Path(__file__).resolve().parents[2]
JOB_PY = ROOT / "workflow" / "i1io" / "table" / "job.py"
WINDOW_PY = ROOT / "ui" / "i1io_table_window.py"

pytestmark = pytest.mark.timeout(120)


# ---- 1. the strip white through the real default factory --------------------------------------
FAKE_HELPER = r'''
import json, sys
argv = sys.argv[1:]
with open(ARGV_FILE, "a", encoding="utf-8") as fp:
    fp.write(json.dumps(argv) + "\n")
def say(ev):
    sys.stdout.write(json.dumps(ev) + "\n"); sys.stdout.flush()
dual = "--i1io-table-dual" in argv
say({"event": "tscan_instrument", "model": "X-Rite i1 Pro 2"})
if dual:
    say({"event": "tdual_state", "dual": True, "kept": False})
for line in sys.stdin:
    try:
        cmd = json.loads(line).get("cmd")
    except ValueError:
        continue
    if cmd == "tscan_calibrate":
        say({"event": "cal_required", "cond": "man_ref_white", "id": "0"})
    elif cmd == "ok":
        if dual:
            say({"event": "tdual_calibration", "ok": True, "lamp_clocks": 523,
                 "uv_clocks": 523})
        say({"event": "tscan_calibrated", "ok": True})
    elif cmd in ("tscan_quit", "quit"):
        say({"event": "tscan_end"})
        break
'''


def _fake_helper(tmp_path: Path) -> "tuple[Path, Path]":
    argv_file = tmp_path / "argv.jsonl"
    exe = tmp_path / "bin" / "chromiq-chartread"
    exe.parent.mkdir(parents=True)
    exe.write_text(f"#!{sys.executable}\nARGV_FILE = {str(argv_file)!r}\n" + FAKE_HELPER,
                   encoding="utf-8")
    exe.chmod(0o755)
    return exe, argv_file


def _job_with_real_factories(tmp_path):
    job = J.TableJob(H.demo_sheet(), folder=tmp_path / "session",
                     open_transport=lambda: None, preflight=lambda: H.OK_PREFLIGHT,
                     other_program=lambda: False)
    # nothing injected: the job's own defaults
    assert job._scan_factory is J._default_scan_reader
    assert job._reader_factory is J._default_reader
    return job


@pytest.mark.parametrize("dual", [False, True], ids=["single", "dual"])
def test_the_strip_white_starts_through_the_real_default_factory(tmp_path, monkeypatch, dual):
    exe, argv_file = _fake_helper(tmp_path)
    monkeypatch.setattr(rd, "helper_path", lambda pkg=None: exe)
    job = _job_with_real_factories(tmp_path)
    if dual:
        job.dual = dl.DualSetup(args=("--dual-scale", "1.1560"), scale=1.156, chosen="M1")
    job._strip_white(tmp_path / "row")          # the 22 Nov TypeError came from here
    started = [json.loads(x) for x in argv_file.read_text(encoding="utf-8").splitlines()]
    assert len(started) == 1
    argv = started[0]
    assert argv[0] == "--json" and argv[-2] == "--i1io-table-scan"
    assert ("--i1io-table-dual" in argv) is dual
    if dual:
        # the dual word comes before the mode, as the helper parses it (reader.ScanReader)
        assert argv.index("--i1io-table-dual") < argv.index("--i1io-table-scan")
        assert job.dual_calibrations["strip"]["ok"] is True
    else:
        assert "strip" not in job.dual_calibrations
    assert job._open_readers == []              # the reader was closed again


def test_the_real_scan_factory_forwards_every_extra_argument(tmp_path, monkeypatch):
    seen = {}

    class Rec:
        def __init__(self, helper, outdir, log, extra_args=()):
            seen.update(helper=helper, outdir=outdir, extra_args=tuple(extra_args))
    monkeypatch.setattr(rd, "ScanReader", Rec)
    monkeypatch.setattr(rd, "helper_path", lambda pkg=None: Path("/fake/chromiq-chartread"))
    J._default_scan_reader(tmp_path, print, extra_args=["--i1io-table-dual", "--x"])
    assert seen["extra_args"] == ("--i1io-table-dual", "--x")
    J._default_scan_reader(tmp_path, print)
    assert seen["extra_args"] == ()


# ---- 2. every call form the job uses binds to the real default -------------------------------
#: the job's injectables (attribute -> the real default the app runs with)
REAL_DEFAULTS = {
    "_reader_factory": J._default_reader,
    "_scan_factory": J._default_scan_reader,
    "_press_factory": J._default_press_factory,
    "_helper_check": J._default_helper_check,
    "_instrument_check": us.instrument_now,
    "_preflight": us.preflight,
    "_open_transport": st.open_table,
}


def _call_forms(path: Path, match) -> "list[tuple[str, int, tuple[str, ...], int]]":
    """(name, positional count, keyword names, line) of every call whose function node
    *match* names (``match(node.func) -> name or None``); a *args / **kw call is refused."""
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        name = match(node.func)
        if name is None:
            continue
        assert not any(isinstance(a, ast.Starred) for a in node.args), (name, node.lineno)
        assert all(k.arg is not None for k in node.keywords), (name, node.lineno)
        out.append((name, len(node.args), tuple(k.arg for k in node.keywords), node.lineno))
    return out


def _self_attr(func) -> "str | None":
    if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
            and func.value.id == "self" and func.attr in REAL_DEFAULTS):
        return func.attr
    return None


def test_every_injectable_call_in_the_job_binds_to_the_real_default():
    forms = _call_forms(JOB_PY, _self_attr)
    # every injectable is called somewhere (a renamed attribute would empty this test)
    assert {f[0] for f in forms} == set(REAL_DEFAULTS)
    bad = []
    for name, npos, kws, line in forms:
        try:
            inspect.signature(REAL_DEFAULTS[name]).bind(*([None] * npos), **dict.fromkeys(kws))
        except TypeError as exc:
            bad.append(f"job.py:{line} self.{name}(...) -> {REAL_DEFAULTS[name].__name__}: {exc}")
    assert not bad, "\n".join(bad)


def test_the_windows_job_factory_calls_bind_to_the_real_factory():
    from ui import i1io_table_window as W

    def match(func):
        if isinstance(func, ast.Name) and func.id in ("JOB_FACTORY", "factory"):
            return func.id
        if isinstance(func, ast.Attribute) and func.attr in ("JOB_FACTORY", "_job_factory"):
            return func.attr
        return None
    forms = _call_forms(WINDOW_PY, match)
    assert forms, "the window no longer calls its job factory by these names"
    sig = inspect.signature(W.default_job_factory)
    for name, npos, kws, line in forms:
        sig.bind(*([None] * npos), **dict.fromkeys(kws))


# ---- 3. every simulated counterpart has the real one's signature -----------------------------
def _params(f) -> "list[tuple[str, str, bool]]":
    return [(p.name, p.kind.name, p.default is not inspect.Parameter.empty)
            for p in inspect.signature(f).parameters.values() if p.name != "self"]


def _sim_window():
    from tests.i1io_table import window_sim
    for obj in vars(window_sim).values():
        if inspect.isclass(obj) and "factory" in vars(obj):
            return obj
    raise AssertionError("tests/i1io_table/window_sim.py has no class with a job factory")


FACTORY_PAIRS = {
    "reader": (J._default_reader, lambda: RS.HelperSim(None).factory()),
    "scan": (J._default_scan_reader, lambda: RS.HelperSim(None).scan_factory()),
    "press": (J._default_press_factory, lambda: RS.HelperSim(None).press_factory()),
    "job": (lambda: __import__("ui.i1io_table_window", fromlist=["x"]).default_job_factory,
            lambda: _sim_window().factory),
}


@pytest.mark.parametrize("pair", sorted(FACTORY_PAIRS))
def test_each_simulated_factory_has_the_real_factorys_signature(pair):
    real, sim = FACTORY_PAIRS[pair]
    if pair == "job":
        real = real()
        assert _params(real) == _params(sim()), pair
        return
    assert _params(real) == _params(sim()), pair


#: (real class, simulated class, constructor compared?) - the simulated readers are built by
#: the factories above with the simulator in front, so their constructors differ on purpose
CLASS_PAIRS = {
    "scan reader": (rd.ScanReader, csim.FakeScanReader),
    "spot reader": (rd.SpotReader, csim.FakeSpotReader),
    "helper process (button)": (rd._Proc, RS.FakePressProc),
    "helper process (spot)": (rd._Proc, RS.FakeHelperProc),
    "table transport": (st.FtdiUsb, ss.SimTransport),
}
#: real public methods a simulation may lack, with the reason
NOT_SIMULATED = {
    ("table transport", "setup"): "called only inside session_table.open_table, which the "
                                  "simulated transport replaces as a whole",
}


def _public(cls) -> "set[str]":
    return {n for n, v in vars(cls).items() if callable(v) and not n.startswith("_")}


@pytest.mark.parametrize("pair", sorted(CLASS_PAIRS))
def test_each_simulated_class_has_the_real_methods_with_their_signatures(pair):
    real, sim = CLASS_PAIRS[pair]
    bad = []
    for name in sorted(_public(real)):
        if not hasattr(sim, name):
            if (pair, name) not in NOT_SIMULATED:
                bad.append(f"{sim.__name__} lacks {name}")
            continue
        if _params(getattr(real, name)) != _params(getattr(sim, name)):
            bad.append(f"{name}: real {_params(getattr(real, name))} "
                       f"sim {_params(getattr(sim, name))}")
    assert not bad, "\n".join(bad)


@pytest.mark.parametrize("pair", sorted(CLASS_PAIRS))
def test_a_method_only_the_simulation_has_is_never_called_by_the_app(pair):
    real, sim = CLASS_PAIRS[pair]
    only = {n for n in _public(sim) if not hasattr(real, n)}
    app = "\n".join(p.read_text(encoding="utf-8")
                    for d in ("workflow/i1io", "ui") for p in (ROOT / d).rglob("*.py"))
    called = sorted(n for n in only if f".{n}(" in app)
    assert not called, f"{sim.__name__}: the app calls {called}, which only the simulation has"
