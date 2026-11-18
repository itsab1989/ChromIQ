"""The i1iO 2 table scan (2026-11-16, merged 2026-11-17; NOT in ChromIQ's UI): the
i1Pro 2's part of one row scan on an X-Rite i1iO 2 table, in the helper,
behind ``--i1io-table-scan``.

Nobody on the project owns the table, so this is proved without hardware:

* the real vendored driver code on a FAKE USB layer
  (native/chartread_helper/tests/i1io_table_scan_test.c) sends, byte for byte,
  what X-Rite's i1Profiler 3.8.6 sent the i1Pro 2 for every row scan in four
  USB recordings of a user's table (44 passes, all the same form), and
  nothing else: no EEPROM write, no scan bit, no ruler bits, no 0xD7;
* once fired, the lamp trigger is always attempted, also after a failed dark
  (the table's pending scan move waits for the lamp);
* "ready" holds the recorded spacing BEFORE the table's move is sent, so the
  fire itself never waits;
* without the switch nothing of it is reachable: the driver file is
  4.3.44's plus one include line, the helper's own code runs only under the
  switch, and the fake-USB wire traces of the lights and ruler harnesses are
  those of the 4.3.44 tree (f486782f0), line for line.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tarfile
import io
from pathlib import Path

import pytest

from tests.test_i1pro3_lights_modes import _build_and_run

ROOT = Path(__file__).resolve().parent.parent
INSTLIB = ROOT / "native" / "instlib"
HELPER = ROOT / "native" / "chartread_helper"
BASE = "f486782f0"          # v4.3.44, helper 2026-11-16d

#: What i1Profiler 3.8.6 sent for every recorded row scan (ChromIQ-work
#: 2026-11-16_i1io_scan_mode/INSTRUMENT_SCAN.md, 44 of 44 passes).
REC_LIGHTS_OFF_CTL = "00000012"
REC_LIGHTS_OFF_BYTES = "000000010000000a00000002003640000001"
REC_DARK = "0000008b00000000000000050000"


def rec_lit(n: int) -> str:
    return "0000008b00000029" + f"{n:08x}" + "0100"


@pytest.fixture(scope="module")
def trace(tmp_path_factory) -> str:
    return _build_and_run(tmp_path_factory, "i1io_table_scan_test")


def _scn(text, scn):
    return [ln.split(" ", 1)[1] for ln in text.splitlines() if ln.startswith(scn + " ")]


def _wire(lines):
    """(kind, request/endpoint, payload) of every request, in order."""
    out = []
    for ln in lines:
        p = ln.split()
        if p[0] == "CTL":
            out.append(("CTL", p[1], p[2]))
        elif p[0] == "WR":
            out.append(("WR", p[1], p[2]))
        elif p[0] == "RD":
            out.append(("RD", p[1], p[2] + p[3] + p[4]))
    return out


def test_a_pass_is_the_recorded_bytes(trace):
    w = _wire(_scn(trace, "pass"))
    assert w == [
        ("CTL", "d6", REC_LIGHTS_OFF_CTL), ("WR", "03", REC_LIGHTS_OFF_BYTES),
        ("CTL", "d4", REC_DARK), ("RD", "82", "1340->1340"),
        ("CTL", "d4", rec_lit(520)), ("RD", "82", "139360->139360"),
        ("CTL", "c9", "in8"),
        ("CTL", "d6", REC_LIGHTS_OFF_CTL), ("WR", "03", REC_LIGHTS_OFF_BYTES),
        ("CTL", "d4", REC_DARK), ("RD", "82", "1340->1340"),
        ("CTL", "d4", rec_lit(1190)), ("RD", "82", "318920->318920"),
        ("CTL", "c9", "in8"),
    ]


def test_the_lights_off_is_the_drivers_own_recorded_off_slow():
    from tests.test_i1pro2_lights_driver import RECORDED
    assert RECORDED["off_slow"] == REC_LIGHTS_OFF_BYTES
    src = (INSTLIB / "cq_i1pro2_tscan.h").read_text(encoding="utf-8")
    assert "cq_lights_seq_off_slow" in src
    assert "static const unsigned char" not in src     # no bytes of its own


def test_nothing_else_is_ever_sent(trace):
    reqs = {(k, r) for k, r, _ in _wire([ln.split(" ", 1)[1] for ln in trace.splitlines()
                                         if " " in ln])}
    assert reqs <= {("CTL", "d6"), ("WR", "03"), ("CTL", "d4"), ("RD", "82"),
                    ("CTL", "c9")}
    for ln in trace.splitlines():
        if " CTL d4 " in ln:
            flags = int(ln.split()[3][-4:], 16)
            assert flags in (0x0000, 0x0100)     # never scan, ruler or UV bits
    src = (INSTLIB / "cq_i1pro2_tscan.h").read_text(encoding="utf-8")
    for forbidden in ("0xC3", "0xD7", "i1pro_writeEEProm", "MMF_SCAN",
                      "RULER", "uicallback", "msec_sleep"):
        assert forbidden not in src, forbidden


def test_the_fire_does_not_wait(trace):
    for ln in trace.splitlines():
        if " FIRE rc=0 " in ln:
            f = dict(kv.split("=") for kv in ln.split()[2:] if "=" in kv)
            assert int(f["ms_dark"]) <= 2          # the dark goes out at once
            assert int(f["ms_lit"]) <= 20          # the lamp right after its data


def test_ready_holds_the_recorded_spacing_before_the_move(trace):
    r = [ln for ln in _scn(trace, "pass") if ln.startswith("READY") or ln.startswith("STEP")]
    assert r[0] == "READY -1 wait=0 why=the lights-off of this pass was not sent"
    assert r[1] == "STEP lights_off"
    assert r[2] == "READY 0 wait=pos why=-"          # lights-off too recent
    assert r[3] == "READY 1 wait=0 why=-"
    assert r[5].startswith("READY -1") and "lights-off" in r[5]   # each pass its own
    assert r[7] == "READY 0 wait=pos why=-"          # the lamp just went dark
    assert r[8] == "READY 1 wait=0 why=-"
    h = (INSTLIB / "cq_tscan.h").read_text(encoding="utf-8")
    assert "#define CQ_TSCAN_LAMPOFF_MS  1070" in h       # recorded min 1.058 s
    assert "#define CQ_TSCAN_LIGHTSOFF_MS 680" in h       # recorded min 0.673 s


@pytest.mark.parametrize("scn", ["darkfail", "darktrigfail"])
def test_a_failed_dark_still_sends_the_lamp_trigger(trace, scn):
    w = _wire(_scn(trace, scn))
    assert ("CTL", "d4", rec_lit(520)) in w
    assert w[-1] == ("CTL", "c9", "in8")
    fire = next(ln for ln in _scn(trace, scn) if ln.startswith("FIRE"))
    assert "rc=1" in fire and "lit_sent=1" in fire and "dark_ev=0x0" not in fire


def test_a_failed_lit_reading_is_reported_and_the_status_still_read(trace):
    fire = next(ln for ln in _scn(trace, "litfail") if ln.startswith("FIRE"))
    assert "rc=1" in fire and "lit_ev=0x72" in fire
    assert _wire(_scn(trace, "litfail"))[-1] == ("CTL", "c9", "in8")


@pytest.mark.parametrize("scn,why", [
    ("range", "reading count out of range"), ("notcal", "not calibrated"),
    ("calold", "the calibration is about to expire"),
    ("spotmode", "not in reflective strip mode"), ("revad", "not an open i1Pro 2")])
def test_refusals(trace, scn, why):
    assert any(ln.startswith("READY -1") and why in ln for ln in _scn(trace, scn))


@pytest.mark.parametrize("scn", ["range", "revad"])
def test_a_refused_fire_sends_nothing(trace, scn):
    lines = _scn(trace, scn)
    i = next(k for k, ln in enumerate(lines) if ln.startswith("STEP fire"))
    assert not [x for x in _wire(lines[i:]) if x[0] in ("CTL", "WR")]
    assert all("rc=-1" in ln for ln in lines if ln.startswith("FIRE"))
    if scn == "revad":                     # not even the lights-off
        assert not _wire(lines)


# ---------------------------------------------------------------------------
# Without the switch: 4.3.44
# ---------------------------------------------------------------------------
def _have_base() -> bool:
    return subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{BASE}^{{commit}}"],
                          capture_output=True).returncode == 0


def _git_show(path: str) -> bytes:
    if not _have_base():
        pytest.skip(f"{BASE} (4.3.44) is not in this clone")
    return subprocess.run(["git", "-C", str(ROOT), "show", f"{BASE}:{path}"],
                          check=True, capture_output=True).stdout


def test_the_driver_file_is_4_3_44s_plus_one_include():
    now = (INSTLIB / "i1pro_imp.c").read_bytes()
    base = _git_show("native/instlib/i1pro_imp.c")
    block = (b"\n/* CHROMIQ PATCH: the i1iO 2 table scan (2026-11-16). ChromIQ's own code in */\n"
             b"/* cq_i1pro2_tscan.h, at the end of the file so that no other recorded patch */\n"
             b"/* is touched; nothing calls it unless ChromIQ's helper is started with */\n"
             b"/* --i1io-table-scan. */\n#include \"cq_i1pro2_tscan.h\"\n")
    # 2026-11-18 (the i1Pro 2 dual scan, step 2): its hooks come after; with
    # them undone the file is 4.3.44's plus this one include, as before
    from tests.test_engine_embeds_a_numeric_calibration import _vendor_module
    text = now.decode("utf-8", "surrogateescape")
    for old, new in reversed(_vendor_module()["I1PRO_IMP_C_DUAL"]):
        assert text.count(new) == 1, old[:60]
        text = text.replace(new, old)
    now = text.encode("utf-8", "surrogateescape")
    assert now.count(block) == 1 and now.endswith(block)
    assert now[:-len(block)] == base


def test_the_vendor_script_reapplies_it():
    text = (ROOT / "scripts" / "vendor_instlib.py").read_text(encoding="utf-8")
    assert "I1PRO_IMP_C_LIGHTS + I1PRO_IMP_C_RULER + I1PRO_IMP_C_TOL + I1PRO_IMP_C_TSCAN" in text
    assert "cq_i1pro2_tscan.h" in text


def test_only_the_switch_reaches_the_new_code():
    src = (HELPER / "chromiq_chartread.c").read_text(encoding="utf-8", errors="replace")
    assert src.count("cq_run_table_scan(") == 1
    assert re.search(r"if \(cq_tscan_dir != NULL\)\n\t\treturn cq_run_table_scan\(", src)
    assert src.count("cq_tscan_dir = argv[ai + 1];") == 1
    assert "static const char *cq_tscan_dir = NULL;" in src
    js = (HELPER / "chromiq_json.c").read_text(encoding="utf-8", errors="replace")
    assert "void (*cq_tscan_line_hook)(const char *line) = NULL;" in js
    ts = (HELPER / "chromiq_tablescan.c").read_text(encoding="utf-8", errors="replace")
    assert ts.count("cq_tscan_line_hook = cq_ts_push;") == 1
    # the driver functions are called from the helper's table-scan file only
    for f in HELPER.glob("*.c"):
        if f.name != "chromiq_tablescan.c":
            assert "i1pro2_cq_tscan_" not in f.read_text(encoding="utf-8", errors="replace"), f
    # and --caps is 4.3.44's, unchanged (the build string is a %s)
    caps = [ln for ln in src.splitlines() if '{\\"caps\\":[' in ln]
    base = [ln for ln in _git_show("native/chartread_helper/chromiq_chartread.c")
            .decode("utf-8", "replace").splitlines() if '{\\"caps\\":[' in ln]
    # 2026-11-18a: one word more, the i1Pro 2 dual-scan conditions (step 1);
    # 2026-11-18c: and its device side (step 2)
    assert caps and base and caps == [base[0].replace(
        '\\"margin_tolerance\\"]',
        '\\"margin_tolerance\\",\\"i1pro2_dual_conditions\\",\\"i1pro2_dual_scan\\",'
        '\\"i1io_table_dual\\"]')]


def test_the_build_string():
    h = (HELPER / "chromiq_ext.h").read_text(encoding="utf-8")
    # 2026-11-17b (round B) = 2026-11-17a + the table drive's button wait;
    # 2026-11-18a = 17b + the i1Pro 2 dual-scan conditions;
    # 2026-11-18b = 18a + the dual scan's resume rule (review fixes);
    # 2026-11-18c = 18b + the dual scan's device side (step 2);
    # 2026-11-18d = 18c + the dual scan's safety fixes (pairing on the instrument path, only
    # recorded UV forms, 41 lamp clocks);
    # 2026-11-18e = 18d + the dual scan on the i1iO 2 table (--i1io-table-dual, --dual-table), last
    assert "chromiq-chartread 2026-11-18e " in h
    assert ("+i1io-table-scan+i1io-press-wait+i1pro2-dual-conditions+i1pro2-dual-resume-rule"
            "+i1pro2-dual-device+i1pro2-dual-safety+i1io-table-dual\"") in h


def _base_tree(tmp: Path) -> Path:
    if not _have_base():
        pytest.skip(f"{BASE} (4.3.44) is not in this clone")
    data = subprocess.run(["git", "-C", str(ROOT), "archive", BASE, "native"],
                          check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        tf.extractall(tmp)
    return tmp / "native" / "chartread_helper"


def _run_target(src: Path, build: Path, target: str) -> str:
    cmake = shutil.which("cmake")
    subprocess.run([cmake, "-S", str(src), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release"],
                   check=True, capture_output=True, timeout=600)
    r = subprocess.run([cmake, "--build", str(build), "--target", target, "-j",
                        str(max(2, (os.cpu_count() or 4) // 2))],
                       capture_output=True, text=True, encoding="utf-8", timeout=900)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    exe = build / target
    r = subprocess.run([str(exe)], capture_output=True, text=True, encoding="utf-8",
                       timeout=300)
    assert r.returncode == 0 and r.stdout.rstrip().endswith("ALL DONE")
    return r.stdout


def _stable(text: str) -> "list[str]":
    """The wire: every request and payload, without timing-only lines."""
    out = []
    for ln in text.splitlines():
        parts = ln.split()
        if len(parts) > 1 and parts[1] in ("CTL", "WR", "RD", "STEP", "RESULT", "END"):
            out.append(" ".join(p for p in parts if not p.startswith("tout=")
                                and not p.startswith("+")))
    return out


#: Every fake-USB harness the helper had before the table scan: the i1Pro 2
#: driver file is the one that gained the include, the others prove that
#: nothing shared (USB layer, helper files) moved either.
EXISTING_HARNESSES = [
    "i1pro_ruler_scan_test", "i1pro2_lights_modes_test", "i1pro2_lights_test",
    "i1pro3_lights_test", "i1pro3_lights_modes_test", "i1pro3_ruler_test",
    "i1pro3_conditions_test", "usb_failure_detail_test",
]


@pytest.fixture(scope="module")
def _trees(tmp_path_factory):
    if sys.platform == "win32" or shutil.which("cmake") is None:
        pytest.skip("built on macOS and Linux only")
    tmp = tmp_path_factory.mktemp("tscan_wire")
    return _base_tree(tmp / "base"), tmp / "b_base", tmp / "b_now"


@pytest.mark.parametrize("target", EXISTING_HARNESSES)
def test_without_the_switch_the_wire_is_4_3_44s(_trees, target):
    base_src, b_base, b_now = _trees
    base = _run_target(base_src, b_base, target)
    now = _run_target(HELPER, b_now, target)
    if _stable(base):
        assert _stable(now) == _stable(base)
    else:
        # harnesses that print results rather than USB requests (the i1Pro 3
        # conditions and ruler records): their whole output, timing tokens out
        assert _whole(base) and _whole(now) == _whole(base)


def _whole(text: str) -> "list[str]":
    return [" ".join(p for p in ln.split() if not p.startswith("tout=")
                     and not p.startswith("+") and not p.startswith("ms="))
            for ln in text.splitlines()]
