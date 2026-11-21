"""The tester program's guarantees, kept for the files that moved into the app.

chromiq-i1io-session 0.6.0 pinned some of its rules by reading its own source files, its README,
its BYTES.md, its zip and its bundled reader. Those tests stayed with the tester (they name files
that are not in the app); the tests in the ``*_ported.py`` files beside this one are the ones that
needed only the moved modules, verbatim. Here the same rules, for the app's copies:

* standard library only (plus the package's own modules; the reader asks ``core.resource_path``
  for ChromIQ's helper, lazily), no em dash;
* the table is written in exactly one place (``Table._write``, through the gate);
* no line id outside the recorded ones exists as a frame, and the start-up ``i0`` only once,
  in the table module;
* no process is ended or started except the read-only ``ioreg`` / ``xattr`` checks;
* the simulators keep their own copy of the steps and their own measured motion start;
* the reader is ChromIQ's own helper, which carries the table-scan mode.

Not carried over, with the reason: the README / BYTES.md / zip / ``bin/`` tests (tester
documents and packaging), the console program's question order (``i1io_session.py``,
``i1io_part_c.py`` did not move: the app's job is a rewrite, plan section 3).
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys

import pytest

from tests.i1io_table import part_c_sim as csim
from tests.i1io_table import session_sim as sim_mod
from tests.i1io_table._moved import MOVED, ROOT, TABLE
from workflow.i1io.table import reader as rd
from workflow.i1io.table import scan as sc
from workflow.i1io.table import session_table as tbl

APP_MODULES = sorted(TABLE.glob("*.py"))
NAMES = {p.name for p in APP_MODULES}


def _src(path) -> str:
    return path.read_text(encoding="utf-8")


#: build step 6 adds the job (job.py), its derived caps (caps.py), the per-system USB checks
#: (usb_system.py) and the session log (diagnostics.py); the five moved modules stay
STEP6_MODULES = {"job.py", "caps.py", "usb_system.py", "diagnostics.py",
                 # build step 7: reading (spot rows, the measurement)
                 "spot.py", "measurement.py",
                 # build step 8: the end of a session, what the next START finds
                 "session_end.py",
                 # round B (build step 10): a strip row's readings into patches, its row file
                 "strip.py",
                 # the i1Pro 2 dual scan on the table (2026-11-18): the dual row's cut, its
                 # files, its pass adapter
                 "dual_rows.py",
                 # 4.3.49: the table's remembered reach (records and learns; never sends)
                 "reach.py",
                 # 4.3.54: the row placement check (a veto on a row's readings; never sends)
                 "placement.py"}


def test_the_package_holds_the_five_moved_modules_and_the_job():
    assert NAMES == {"__init__.py", "session_table.py", "geometry.py", "lines.py", "scan.py",
                     "reader.py"} | STEP6_MODULES


STDLIB = {"__future__", "csv", "json", "os", "time", "dataclasses", "pathlib", "math", "random",
          "re", "queue", "subprocess", "sys", "threading", "plistlib", "signal", "ctypes",
          "usb",          # pyusb: imported only inside open_table, when a real table is opened
          "copy",         # job.py: its own copy of the chart (review of step 6)
          "getpass",      # diagnostics.py: the user's name, only to keep it OUT of the log
          "io", "shutil",  # step 7: the readings' CSV; one copy of the measurement on Save
          "hashlib",       # review 8, S-4: the filing note's checksum of the measurement
          "struct",        # D-4b: the table's 36 stored white tile values (bytes 88-231 only)
          # 4.3.49 (reach.py): the table's salted key, and the salt made on this computer
          "hmac", "secrets",
          # 4.3.54 (placement.py): the run medians, kept sorted as they grow
          "bisect"}
#: step 7: the measurement is made with the APP's own functions for a measurement (the
#: i1Profiler import's pairing, the measurement states, the atomic replace), never a second
#: writer of its own; nothing else of the app is imported
STEP7_APP_IMPORTS = {
    "measurement.py": {"workflow.measurement_pairing", "workflow.measurement_state",
                       "core.text_io", "core.file_manager",
                       # D-4b: a row's XYZ again from its scaled spectrum, as strip.py does
                       "workflow.argyll_colorimetry"},
    # round B: a strip row's XYZ from its spectrum, by the app's own ArgyllCMS method
    "strip.py": {"workflow.argyll_colorimetry", "core.cgats_date"},
    # round B: the helper's build string through the app's own --caps question
    "reader.py": {"workflow.chartread_engine"},
    "job.py": {"workflow.measurement_state",
               # A10 (4.3.50): who wrote the measurement, into its header, before the filing
               # note (a file on disk; the helper's build is a cached string, never a start)
               "workflow.ti3_provenance", "workflow.chartread_engine",
               # step 8: Save is guarded as every measurement is (old/ copy, C0 -> C)
               "workflow.measurement_session",
               # the i1Pro 2 dual scan on the table (2026-11-18): the hand dual scan's own files
               # and records, never a second mechanism (its storage rules, its pass record, the
               # i1Pro 3 Beta's condition files, the measurement's condition keyword, the run)
               "workflow.dual_scan.storage", "workflow.dual_scan.record",
               "workflow.i1pro3_conditions", "workflow.measurement_condition",
               "core.file_manager"},
    # the dual scan: M1 / M2 assembled from the base's condition files (the i1Pro 3 Beta's)
    "measurement.py": {"workflow.measurement_pairing", "workflow.measurement_state",
                       "core.text_io", "core.file_manager", "workflow.argyll_colorimetry",
                       "workflow.i1pro3_conditions"},
    # the dual scan's header keywords, as storage names them
    "dual_rows.py": {"workflow.dual_scan.storage"},
    # 4.3.54: the row placement check (the row placement study's method (d)): numpy, as the
    # app already uses it, the dual scan's own spectrum -> Lab (the study's), the app's
    # ArgyllCMS method for other band sets, the app's CIEDE2000; all imported lazily, inside
    # the check, so loading the package stays standard library only
    "placement.py": {"numpy", "workflow.dual_scan.colour", "workflow.argyll_colorimetry",
                     "workflow.profile_engine.metrics"},
}


@pytest.mark.parametrize("path", APP_MODULES + [MOVED["i1io_session_sim.py"],
                                               MOVED["i1io_part_c_sim.py"]],
                         ids=lambda p: p.name)
def test_standard_library_only_and_no_em_dash(path):
    src = _src(path)
    assert "—" not in src, path.name
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:                       # the package's own siblings
                assert (node.module is None and all(a.name + ".py" in NAMES
                                                    for a in node.names)) or \
                    (node.module or "") + ".py" in NAMES, (path.name, ast.dump(node))
                continue
            mods = [node.module or ""]
        else:
            continue
        for m in mods:
            top = m.split(".")[0]
            ok = (top in STDLIB or m.startswith("workflow.i1io.table")
                  or m.startswith("tests.i1io_table")
                  or (path.name == "reader.py" and m == "core.resource_path")
                  # step 6: the table is opened only through ChromIQ's own USB library
                  or (path.name in ("session_table.py", "usb_system.py")
                      and m == "core.usb_library")
                  # step 6 (owner's ruling): on Windows the table's driver state is read from
                  # the installer's own knowledge (read only)
                  or (path.name in ("session_table.py", "usb_system.py")
                      and m == "core.usb_driver_installer")
                  or m in STEP7_APP_IMPORTS.get(path.name, ()))
            assert ok, (path.name, m)


def test_the_reader_reaches_chromiq_only_for_the_helper_path():
    tree = ast.parse(_src(TABLE / "reader.py"))
    outside = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
               and (n.module or "").startswith("core")]
    assert len(outside) == 1 and outside[0].module == "core.resource_path"
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "helper_path")
    assert outside[0] in list(ast.walk(fn))       # inside helper_path, nowhere else


def test_the_table_is_written_in_one_place_only():
    src = _src(TABLE / "session_table.py")
    assert src.count("self.t.write(") == 1
    assert src.count("self.dev.write(") == 1
    assert len(re.findall(r"ctrl_transfer\(", src)) == 1
    for name in ("geometry.py", "lines.py", "scan.py", "reader.py") + tuple(sorted(STEP6_MODULES)):
        s = _src(TABLE / name)
        assert ".t.write(" not in s and "dev.write(" not in s and "ctrl_transfer" not in s, name


FORBIDDEN_AS_FIXED_FRAMES = ("m2", "c3", "c4", "d1", "a3", "p1")


def test_only_the_recorded_frames_exist_and_the_start_up_once():
    src = _src(TABLE / "session_table.py")
    for cid in FORBIDDEN_AS_FIXED_FRAMES:
        assert f'_frame("{cid}"' not in src, cid
    frames = re.findall(r'_frame\("([a-z][0-9])"(?:, "([0-9a-f]*)")?\)', src)
    assert sorted({f for f, _ in frames}) == sorted({"a1", "k2", "u8", "a0", "s0", "f4", "p0",
                                                     "i1", "f0", "f3", "m0", "f1", "m1", "i0"})
    assert [a for f, a in frames if f == "i0"] == [""]
    calls = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) == "_frame"]
    assert all(all(isinstance(a, ast.Constant) for a in c.args) for c in calls)
    assert len(calls) == 46
    assert src.count('_frame("i0")') == 1
    for name in ("geometry.py", "lines.py", "scan.py", "reader.py"):
        assert ";i02c" not in _src(TABLE / name), name


def test_no_process_is_ended_and_only_the_read_only_checks_are_run():
    for path in APP_MODULES:
        src = _src(path)
        for bad in ("os.kill", "killpg", "pkill", "killall", "launchctl", "os.system"):
            assert bad not in src, (path.name, bad)
    runs = re.findall(r"subprocess\.run\(\s*(\[[^\]]*\])", "".join(_src(p) for p in APP_MODULES))
    # step 6: usb_system.py looks for i1Profiler through run=_run (pgrep / tasklist), read only
    us = _src(TABLE / "usb_system.py")
    assert re.findall(r'run\((\["(?:pgrep|tasklist)"[^\]]*\])\)', us) == [
        '["pgrep", "-x", "-i", "i1Profiler"]', '["pgrep", "-f", "i1Profiler.app/Contents/MacOS"]',
        '["tasklist", "/FI", "IMAGENAME eq i1Profiler.exe", "/FO", "CSV", "/NH"]']
    assert sorted(runs) == sorted([
        '["/usr/sbin/ioreg", "-a", "-r", "-c", "IOUSBHostDevice", "-l"]',
        '["/usr/bin/xattr", "-p", "com.apple.quarantine", str(path)]',
        '["/usr/sbin/ioreg", "-a", "-r", "-c", "IOUSBHostDevice", "-l"]'])
    # the helper itself is started by the reader's own process wrapper only
    assert "Popen(" not in "".join(_src(TABLE / n) for n in ("session_table.py", "geometry.py",
                                                             "lines.py", "scan.py"))


def test_the_simulator_carries_its_own_copy_of_every_step():
    src = _src(MOVED["i1io_session_sim.py"])
    assert "tbl." not in src and src.count("workflow.i1io.table.session_table") == 1
    assert ("from workflow.i1io.table.session_table import TransportError, checksum, "
            "checksum_ok") in src
    assert sim_mod.REC_OPEN == [tbl.WIRE[k].decode().rstrip("\r") for k in tbl.OPEN_KEYS]
    for s in tbl.STEPS:
        assert sim_mod.REC_STEPS[s.key] == [tbl.WIRE[k].decode().rstrip("\r")
                                            for k in tbl.step_lines(s)], s.key


def test_the_part_c_simulator_keeps_its_own_motion_start():
    assert csim.TABLE_MOTION_START_AFTER_LAMP_S == 0.372
    assert sc.MOTION_START_AFTER_LAMP_S == 0.372 and sc.CUT_REFINE_READINGS == 0
    assert "MOTION_START_AFTER_LAMP_S" not in _src(MOVED["i1io_part_c_sim.py"]).replace(
        "TABLE_MOTION_START_AFTER_LAMP_S", "")


def test_the_reader_is_chromiqs_own_helper_with_the_table_scan_mode():
    path = rd.helper_path()
    assert path == ROOT / "native" / ("chromiq-chartread.exe" if sys.platform == "win32"
                                      else "chromiq-chartread")
    if sys.platform != "darwin":
        pytest.skip("the committed helper is the macOS build")
    data = path.read_bytes()
    assert f"chromiq-chartread {rd.HELPER_BUILD} ".encode() in data
    assert b"--i1io-table-scan" in data and b"+i1io-table-scan" in data
    h = (ROOT / "native" / "chartread_helper" / "chromiq_ext.h").read_text(encoding="utf-8")
    assert f'"chromiq-chartread {rd.HELPER_BUILD} ' in h
    archs = subprocess.run(["lipo", "-archs", str(path)], capture_output=True, text=True,
                           encoding="utf-8", timeout=30).stdout.split()
    assert sorted(archs) == ["arm64", "x86_64"]


def test_a_tester_package_folder_still_names_its_own_bin(tmp_path):
    from core.resource_path import argyll_binary
    assert rd.helper_path(tmp_path) == tmp_path / "bin" / argyll_binary("chromiq-chartread")
