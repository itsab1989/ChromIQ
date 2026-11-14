"""The i1Pro 2 indicator lights (Preferences > Beta, 2026-11-13): the driver.

Nobody on the project owns an i1Pro 2, so the patch to the vendored ArgyllCMS
driver (native/instlib/i1pro_imp.c, i1pro_imp.h, i1pro.c; recorded in
scripts/vendor_instlib.py PATCHES and native/instlib/PROVENANCE.md) is proved
here without hardware:

* the three sequences it can send are, byte for byte, the ones a user's
  recording of X-Rite's i1Profiler 3.8.6 showed on his own i1Pro 2 Rev E, and
  an independent decoder reads them as "white" and two forms of "off";
* the patch adds no other request: no EEPROM write, no second 0xD6 sender,
  nothing that can reach Argyll's own (uncalled) light functions; every
  trigger of the driver passes the off guard; i1Pro 3, ColorMunki and every
  other driver are byte-identical to upstream;
* undoing the recorded patches gives Argyll's own files back, sha for sha;
* the real driver on a fake USB layer: with the option off it puts
  exactly what Argyll's own unpatched driver puts on the wire, for an i1Pro 2,
  an original i1Pro and an i1Monitor; with it on, the white / off order, the
  gates, the failure rule and the close are what the design says.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INSTLIB = ROOT / "native" / "instlib"
HELPER_SRC = ROOT / "native" / "chartread_helper"

#: The three sequences as the recording shows them, on bulk endpoint 0x03
#: after request 0xD6 (ChromIQ-work/2026-11-13_issue129_records/i1pro2_side,
#: RESULTS.md section 3 and dump_R1.txt 83.497 / 84.050 / 0.053):
RECORDED = {
    # at open, after the EEPROM read and the chip id
    "white": "000000020000000a000000010036400000010000000affffffff3f3640000001",
    # before every calibration and every scan pass
    "off_slow": "000000010000000a00000002003640000001",
    # when i1Profiler let the instrument go, 6 ms before EEPROM reads
    "off_now": "000000010000000700000002000001",
}
#: Argyll's own i1pro2_indLEDoff bytes, never seen on the wire.
ARGYLL_OFF = "000000010000000700000001000010"

C_ARRAYS = {"white": "cq_lights_seq_white", "off_slow": "cq_lights_seq_off_slow",
            "off_now": "cq_lights_seq_off_now"}


def _src(name: str) -> str:
    return (INSTLIB / name).read_text(encoding="utf-8", errors="surrogateescape")


def _c_array(text: str, name: str) -> bytes:
    m = re.search(r"static const unsigned char " + name +
                  r"\[(\d+)\] = \{(.*?)\};", text, re.S)
    assert m, f"{name} is not in i1pro_imp.c"
    body = re.sub(r"/\*.*?\*/", "", m.group(2), flags=re.S)
    data = bytes(int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]{2})", body))
    assert len(data) == int(m.group(1)), f"{name}: declared size differs"
    return data


def _decode(seq: bytes) -> "list[dict]":
    """Argyll's format (i1pro_imp.c, the comment above i1pro2_indLEDseq),
    decoded independently of the C code: u32 block count, then per block u32
    byte count (including the repeat word), u32 repeat (FFFFFFFF = forever),
    then 3-byte steps: LED mask, u16 clocks. Raises on any inconsistency."""
    def u32(i):
        return int.from_bytes(seq[i:i + 4], "big")
    nblocks, i, blocks = u32(0), 4, []
    for _ in range(nblocks):
        nbytes, repeat = u32(i), u32(i + 4)
        steps_raw = seq[i + 8:i + 4 + nbytes]
        assert (nbytes - 4) % 3 == 0 and len(steps_raw) == nbytes - 4
        steps = [(steps_raw[k], int.from_bytes(steps_raw[k + 1:k + 3], "big"))
                 for k in range(0, len(steps_raw), 3)]
        blocks.append({"repeat": repeat, "steps": steps})
        i += 4 + nbytes
    assert i == len(seq), "trailing bytes"
    return blocks


# ---------------------------------------------------------------------------
# The bytes
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("which", sorted(RECORDED))
def test_each_sequence_is_the_recorded_bytes(which):
    assert _c_array(_src("i1pro_imp.c"), C_ARRAYS[which]).hex() == RECORDED[which]


def test_the_sequences_mean_white_and_off():
    white = _decode(bytes.fromhex(RECORDED["white"]))
    assert [b["repeat"] for b in white] == [1, 0xFFFFFFFF]
    assert {m for m, _t in white[0]["steps"]} == {0x00}       # dark first
    assert {m for m, _t in white[1]["steps"]} == {0x3F, 0x00}  # all six LEDs
    for off in ("off_slow", "off_now"):
        blocks = _decode(bytes.fromhex(RECORDED[off]))
        assert len(blocks) == 1 and blocks[0]["repeat"] == 2   # ends by itself
        assert {m for m, _t in blocks[0]["steps"]} == {0x00}   # no LED, ever
    slow = sum(t for _m, t in _decode(bytes.fromhex(RECORDED["off_slow"]))[0]["steps"])
    assert 2 * slow * 73e-6 < 2.5    # plays ~2 s: CQ_LIGHTS_SLOW_MS covers it


def test_argylls_own_off_bytes_are_not_used():
    text = _src("i1pro_imp.c")
    for name in C_ARRAYS.values():
        assert _c_array(text, name).hex() != ARGYLL_OFF


# ---------------------------------------------------------------------------
# What the patch adds, and what it does not
# ---------------------------------------------------------------------------
def _vendor():
    from tests.test_engine_embeds_a_numeric_calibration import _vendor_module
    return _vendor_module()


def _upstream_text(dest: str) -> str:
    """The vendored file with every recorded patch undone."""
    text = _src(dest)
    for old, new in reversed(_vendor()["PATCHES"].get(dest, [])):
        assert text.count(new) == 1, f"{dest}: a recorded patch is not in the tree once"
        text = text.replace(new, old)
    return text


#: The vendored files the lights patches touch, written back to Argyll's own
#: text for the upstream build of the fake-USB tests.
UPSTREAM_FILES = ("i1pro_imp.c", "i1pro_imp.h", "i1pro.c",
                  "i1pro3_imp.c", "i1pro3_imp.h", "i1pro3.c")


def _provenance_upstream_sha() -> "dict[str, str]":
    prov = (INSTLIB / "PROVENANCE.md").read_text(encoding="utf-8")
    return dict(re.findall(r"^\| `([^`]+)` \| `[^`]+` \| `([0-9a-f]{16})…` \|$",
                           prov.split("## Files", 1)[1], re.M))


@pytest.mark.parametrize("dest", ["i1pro_imp.c", "i1pro_imp.h", "i1pro.c"])
def test_undoing_the_patches_gives_argylls_own_file_back(dest):
    up = _upstream_text(dest).encode("utf-8", "surrogateescape")
    assert hashlib.sha256(up).hexdigest()[:16] == _provenance_upstream_sha()[dest]


def _added_lines(dest: str) -> "list[str]":
    """The lines the LIGHTS patches add (the ruler check's patches, which share
    these files since 2026-11-14, are pinned in tests/test_ruler_driver.py)."""
    v = _vendor()
    ruler = [pt for k in ("I1PRO_IMP_H_RULER", "I1PRO_IMP_C_RULER",
                          "I1PRO3_IMP_H_RULER", "I1PRO3_IMP_C_RULER")
             for pt in v.get(k, [])]
    added = []
    for old, new in v["PATCHES"].get(dest, []):
        if (old, new) in ruler:
            continue
        o = set(old.splitlines())
        added += [ln for ln in new.splitlines() if ln not in o]
    return added


def test_the_patch_adds_no_other_request():
    code = "\n".join(_added_lines("i1pro_imp.c") + _added_lines("i1pro.c")
                     + _added_lines("i1pro_imp.h"))
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    # one request, 0xD6, and its one bulk write on endpoint 0x03
    assert re.findall(r"0x[Dd]6|0x[Cc][0-9A-Fa-f]|0x[Dd][0-9A-Fa-f]", code) == ["0xD6"]
    assert code.count("usb_control(") == 1 and code.count("usb_write(") == 1
    assert "0x03, (unsigned char *)seq" in code
    for never in ("usb_read(", "writeEEProm", "readEEProm", "update_log",
                  "ENABLE_WRITE", "i1pro2_indLEDseq", "i1pro2_indLEDoff",
                  "triggermeasure", "reset("):
        assert never not in code, never


def _without_never_blocks(text: str) -> str:
    """Drop every `#ifdef NEVER ... #endif` region (nesting-aware)."""
    out, depth, never_at = [], 0, None
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith(("#if", "#ifdef", "#ifndef")):
            depth += 1
            if never_at is None and re.match(r"#ifdef\s+NEVER\b", s):
                never_at = depth
            continue
        if s.startswith("#endif"):
            if never_at == depth:
                never_at = None
            depth -= 1
            continue
        if never_at is None:
            out.append(ln)
    return "\n".join(out)


def test_argylls_own_light_functions_stay_uncalled():
    live = _without_never_blocks(_src("i1pro_imp.c"))
    # i1pro2_indLEDseq: its definition and the call in i1pro2_indLEDoff only;
    # i1pro2_indLEDoff: its definition only.
    assert len(re.findall(r"\bi1pro2_indLEDseq\s*\(", live)) == 2
    assert len(re.findall(r"\bi1pro2_indLEDoff\s*\(", live)) == 1
    assert "0xD6" in live
    assert len(re.findall(r"0xD6", live)) == 2      # Argyll's sender and ours


def test_every_trigger_passes_the_off_guard():
    text = _src("i1pro_imp.c")
    body = text[text.index("\ni1pro_trigger_one_measure(\n"):]
    body = body[:body.index("\n}\n")]
    # the guard comes before anything the function does
    assert body.index("i1pro2_cq_lights_trigger(p);") < body.index("*inttime < m->min_int_time")
    live = _without_never_blocks(text)
    for trig in ("i1pro_triggermeasure(p, TRIG_DELAY)", "i1pro2_triggermeasure(p, TRIG_DELAY)"):
        assert live.count(trig) == 1 and trig in body
    # the off before an EEPROM read, and the end at the close
    rd = text[text.index("\ni1pro_readEEProm(\n"):]
    rd = rd[:rd.index("\n}\n")]
    assert rd.index("i1pro2_cq_lights_eeprom(p);") < rd.index("0xC4")
    dl = text[text.index("void del_i1proimp(i1pro *p) {"):]
    dl = dl[:dl.index("\n}\n")]
    assert dl.index("i1pro2_cq_lights_end(p);") < dl.index("i1pro_terminate_switch(p)")


def test_white_follows_every_measure_and_calibrate_in_i1pro_c():
    """The ready hook follows every calibration; every reading sits between
    the reading hooks (2026-11-13: ..._after_read calls ..._ready unless the
    result signals were chosen, so with both choices off this is 4.3.33's
    ready, tests/test_i1pro2_lights_modes.py proves it on the wire)."""
    text = _src("i1pro.c")
    for call in ("rv = i1pro_imp_measure(p, vals, npatch, instClamp);\n",
                 "rv = i1pro_imp_measure(p, val, 1, clamp);\n"):
        i = text.index(call)
        before = text[:i].rstrip("\t").splitlines()[-1]
        assert before.lstrip("\t").startswith("i1pro2_cq_lights_reading(p, 1);")
        after = text[i + len(call):].lstrip("\t")
        assert after.startswith("i1pro2_cq_lights_after_read(p);")
    call = "rv = i1pro_imp_calibrate(p, calt, calc, idtype, id);\n"
    i = text.index(call) + len(call)
    assert text[i:].lstrip("\t").startswith("i1pro2_cq_lights_ready(p);")


def test_every_entry_asks_dtype_first():
    text = _src("i1pro_imp.c")
    block = text[text.index("CHROMIQ PATCH: the i1Pro 2 indicator lights"):]
    entries = re.findall(r"\n(?:void|int) (i1pro2_cq_lights_\w+)\(void \*pp", block)
    assert {"i1pro2_cq_lights_trigger", "i1pro2_cq_lights_eeprom",
            "i1pro2_cq_lights_ready", "i1pro2_cq_lights_end",
            "i1pro2_cq_lights_reading", "i1pro2_cq_lights_after_read",
            "i1pro2_cq_lights_owe", "i1pro2_cq_lights_owed_ms",
            "i1pro2_cq_lights_result", "i1pro2_cq_lights_choices",
            "i1pro2_cq_lights_options", "i1pro2_cq_lights_begin"} <= set(entries)
    for fn in entries:
        body = block[re.search(r"\n(?:void|int) " + fn + r"\(void \*pp", block).start():]
        body = body[:body.index("\n}\n")]
        if fn in ("i1pro2_cq_lights_begin", "i1pro2_cq_lights_options"):
            assert "p->dtype != instI1Pro2" in body, fn
            assert body.index("p->dtype != instI1Pro2") < body.index("p->m"), fn
        else:
            assert "cq_lights_m(p)" in body, fn
    helper = block[block.index("static i1proimp *cq_lights_m(i1pro *p) {"):]
    helper = helper[:helper.index("\n}\n")]
    assert helper.index("p->dtype != instI1Pro2") < helper.index("p->m")
    begin = block[block.index("int i1pro2_cq_lights_begin(void *pp) {"):]
    begin = begin[:begin.index("\n}\n")]
    for gate in ("p->dtype != instI1Pro2", "!p->inited", "I1PRO_CAP2_IND_LED"):
        assert gate in begin


def test_no_other_driver_is_touched():
    patched = set(_vendor()["PATCHES"])
    assert patched == {"rspl1.c", "conv.c", "i1pro_imp.c", "i1pro_imp.h", "i1pro.c",
                       "i1pro3_imp.c", "i1pro3_imp.h", "i1pro3.c"}
    up = _provenance_upstream_sha()
    for name in ("munki_imp.c",
                 "munki.c", "i1d3.c", "ss_imp.c", "dtp20.c", "icoms.c",
                 "usbio.c", "inst.c"):
        have = hashlib.sha256((INSTLIB / name).read_bytes()).hexdigest()[:16]
        assert have == up[name], name


# ---------------------------------------------------------------------------
# The real driver on a fake USB layer (two small builds of the library)
# ---------------------------------------------------------------------------
def _cmake() -> str:
    if sys.platform == "win32":
        pytest.skip("the fake-USB driver test is built on macOS and Linux only: "
                    "chromiq-chartread helper not built here with the "
                    "Windows toolchain")
    exe = shutil.which("cmake")
    if exe is None:
        pytest.skip("cmake not available: the chromiq-chartread helper not "
                    "built here")
    return exe


def build_and_run(tmp_path_factory, stem: str) -> "dict[str, str]":
    """Build `<stem>` and `<stem>_upstream` (Argyll's own unpatched i1Pro
    files, checked against PROVENANCE's sha256) and return both traces."""
    cmake = _cmake()
    work = tmp_path_factory.mktemp(stem + "_build")
    updir = work / "upstream"
    updir.mkdir()
    sha = _provenance_upstream_sha()
    for dest in UPSTREAM_FILES:
        data = _upstream_text(dest).encode("utf-8", "surrogateescape")
        assert hashlib.sha256(data).hexdigest()[:16] == sha[dest]
        (updir / dest).write_bytes(data)
    build = work / "build"
    env = dict(os.environ)
    subprocess.run([cmake, "-S", str(HELPER_SRC), "-B", str(build),
                    "-DCMAKE_BUILD_TYPE=Release",
                    f"-DCQ_UPSTREAM_I1PRO_DIR={updir}"],
                   check=True, capture_output=True, timeout=600, env=env)
    jobs = str(max(2, (os.cpu_count() or 4) // 2))
    for target in (stem, stem + "_upstream"):
        r = subprocess.run([cmake, "--build", str(build), "--target", target,
                            "-j", jobs], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=900,
                           env=env)
        assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    out = {}
    for name, target in (("patched", stem), ("upstream", stem + "_upstream")):
        exe = next(p for p in build.rglob(target + "*")
                   if p.is_file() and os.access(p, os.X_OK)
                   and p.name in (target, target + ".exe"))
        r = subprocess.run([str(exe)], capture_output=True, text=True,
                           encoding="utf-8", timeout=120)
        assert r.returncode == 0 and r.stdout.rstrip().endswith("ALL DONE"), \
            r.stdout[-2000:] + r.stderr[-2000:]
        out[name] = r.stdout
    return out


@pytest.fixture(scope="module")
def traces(tmp_path_factory):
    return build_and_run(tmp_path_factory, "i1pro2_lights_test")


def _scenario(trace: str, name: str) -> "list[str]":
    return [ln.split(" ", 1)[1] for ln in trace.splitlines()
            if ln.startswith(name + " ")]


def _wire(lines):
    """Only what reaches the instrument: control requests, writes, reads."""
    return [ln for ln in lines if ln.split(" ", 1)[0] in ("CTL", "WR", "RD")]


def _d6(lines):
    return [ln for ln in lines if ln.startswith(("CTL d6", "WR 03"))]


WHITE = ["CTL d6 00000020 tout=0.25", f"WR 03 {RECORDED['white']} tout=0.25"]
OFF_SLOW = ["CTL d6 00000012 tout=0.25", f"WR 03 {RECORDED['off_slow']} tout=0.25"]
OFF_NOW = ["CTL d6 0000000f tout=0.25", f"WR 03 {RECORDED['off_now']} tout=0.25"]
OFF_CLOSE = ["CTL d6 0000000f tout=0.50", f"WR 03 {RECORDED['off_now']} tout=0.50"]


@pytest.mark.parametrize("scn", ["off_i1pro2", "off_i1pro", "off_i1monitor"])
def test_option_off_puts_on_the_wire_exactly_what_argyll_does(traces, scn):
    patched = _scenario(traces["patched"], scn)
    upstream = _scenario(traces["upstream"], scn)
    assert upstream and patched == upstream
    assert _d6(patched) == []


@pytest.mark.parametrize("scn", ["on_i1pro", "on_i1monitor", "on_no_led_bit",
                                 "on_not_inited", "forced_state_i1pro"])
def test_option_on_sends_nothing_to_anything_but_a_ready_i1pro2(traces, scn):
    lines = _scenario(traces["patched"], scn)
    assert lines and _d6(lines) == []
    assert "BEGIN 1" not in lines


def test_option_off_on_an_i1pro2_is_the_option_on_session_minus_the_lights(traces):
    off = _wire(_scenario(traces["patched"], "off_i1pro2"))
    on = [ln for ln in _wire(_scenario(traces["patched"], "on_i1pro2"))
          if not ln.startswith(("CTL d6", "WR 03"))]
    assert on == off


def test_option_on_a_whole_i1pro2_session(traces):
    lines = _scenario(traces["patched"], "on_i1pro2")
    w = _wire(lines)
    trig = "CTL d4 0000022c00000029000000010100 tout=2.00"
    eeprom = ["CTL c4 00000c140040 tout=2.00", "RD 82 64"]
    assert w == (WHITE                       # begin: ready
                 + OFF_SLOW + [trig]         # calibration's first trigger
                 + [trig]                    # its second: already off
                 + WHITE                     # calibration returned
                 + OFF_SLOW + [trig]         # the strip
                 + WHITE                     # the strip returned
                 + OFF_NOW + eeprom          # nothing may play during a read
                 + WHITE                     # ready again
                 + OFF_CLOSE)                # the close
    # every trigger comes after an off (or after nothing lit)
    lit = False
    for ln in w:
        if ln == WHITE[1]:
            lit = True
        elif ln.startswith("WR 03"):
            lit = False
        elif ln.startswith("CTL d4") or ln.startswith("CTL c4"):
            assert not lit, ln


def test_a_failed_request_is_noted_once_and_ends_the_lights(traces):
    lines = _scenario(traces["patched"], "fail_off")
    assert [ln for ln in lines if ln.startswith("NOTE")] == ["NOTE seq=2 err=0x200"]
    d6 = _d6(lines)
    assert d6 == WHITE + ["CTL d6 00000012 tout=0.25"]   # nothing after it
    assert sum(ln.startswith("CTL d4") for ln in lines) == 3   # measuring went on
    white = _scenario(traces["patched"], "fail_white")
    assert [ln for ln in white if ln.startswith("NOTE")] == ["NOTE seq=1 err=0x0"]
    assert "BEGIN 0" in white and _d6(white) == WHITE
    assert sum(ln.startswith("CTL d4") for ln in white) == 3


def test_the_end_paths(traces):
    end = _scenario(traces["patched"], "end_cmd")
    assert _d6(end) == WHITE + OFF_CLOSE             # off, then never again
    assert sum(ln.startswith("CTL d4") for ln in end) == 1
    assert _d6(_scenario(traces["patched"], "begin_twice")) == WHITE + OFF_CLOSE
    # closed while an OFF_SLOW may still play: an OFF_NOW at the close
    assert _d6(_scenario(traces["patched"], "close_after_trigger")) == \
        WHITE + OFF_SLOW + OFF_CLOSE


def test_white_waits_for_a_pending_trigger(traces):
    lines = _scenario(traces["patched"], "trigger_pending")
    i_ready = lines.index("STEP ready")
    i_read = lines.index("STEP read-starts")
    assert _d6(lines[i_ready:i_read]) == []
    # the trigger thread really was still waiting while ready() ran
    assert any(ln.startswith("CTL d4") for ln in lines[i_read:])
    assert not any(ln.startswith("CTL d4") for ln in lines[:i_read])
