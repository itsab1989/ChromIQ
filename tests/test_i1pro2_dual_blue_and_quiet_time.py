"""4.3.52: the i1Pro 2 lights Beta's blue before the return pass of a dual scan,
and the quiet time before a reading as a setting of its own.

The owner, 2026-11-20: "yes build the blue light, are we too cautious with our
waiting time at the moment?" and "could we allow the user to set the timing
himself with recommendations of what was measured inside i1profiler and leave
more room than that to the bottom end?". The study (ChromIQ-work
2026-11-20_pulse452b/quiet_study.txt) keeps 2.1 s as the default.

Proved here on a FAKE USB layer through the REAL vendored driver
(native/chartread_helper/tests/i1pro2_dual_lights_test.c), and against ChromIQ
4.3.51's i1pro.c / i1pro_imp.c / i1pro_imp.h for every life that asks for
nothing new:

* the blue is the recorded 0xD6 + 702 bytes on 0x03, sent after the lamp pass
  and before the return pass's first trigger, and nothing else changes;
* it is refused (nothing on the wire) without the lights, without result
  signals, outside the return pass's wait, in a single scan, once the button
  was pressed, and a second time in one wait;
* the user's quiet time changes only how long the next trigger waits;
* after the blue alone the next trigger waits the blue's own 370 ms
  (i1Profiler's shortest recorded gap after that program, fix round), and any
  later write gives the user's quiet time back;
* everything else on the wire is 4.3.51's, byte for byte.

And the helper's and the app's side: the 550 ms, the skip, the flag, the
setting, Preferences, the log lines and the session header.
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
HELPER_SRC = ROOT / "native" / "chartread_helper"
INSTLIB = ROOT / "native" / "instlib"
BLUE_SHA256 = "f848b4e7f588225ab4af171034b582764da75d687527592a20a420e3acd6d202"


@pytest.fixture(scope="module")
def traces(tmp_path_factory) -> "dict[str, str]":
    if sys.platform == "win32":
        pytest.skip("the fake-USB driver tests are built on macOS and Linux only")
    cmake = shutil.which("cmake")
    if cmake is None:
        pytest.skip("cmake not available: the helper is not built here")
    tmp = tmp_path_factory.mktemp("dualblue")
    dirs = {}
    # 4.3.53: also against 4.3.52's driver (tests/test_instrument_waits.py reads it)
    for tag in ("v4.3.51", "v4.3.52"):
        old = tmp / tag.replace(".", "")
        old.mkdir()
        for f in ("i1pro.c", "i1pro_imp.c", "i1pro_imp.h"):
            r = subprocess.run(["git", "-C", str(ROOT), "show", f"{tag}:native/instlib/{f}"],
                               capture_output=True, timeout=60)
            if r.returncode != 0:
                pytest.skip(f"the {tag} tag is not in this checkout")
            (old / f).write_bytes(r.stdout)
        dirs[tag] = old
    build = tmp / "build"
    subprocess.run([cmake, "-S", str(HELPER_SRC), "-B", str(build),
                    "-DCMAKE_BUILD_TYPE=Release", f"-DCQ_V4351_I1PRO_DIR={dirs['v4.3.51']}",
                    f"-DCQ_V4352_I1PRO_DIR={dirs['v4.3.52']}"],
                   check=True, capture_output=True, timeout=600)
    jobs = str(max(2, (os.cpu_count() or 4) // 2))
    targets = ("i1pro2_dual_lights_test", "i1pro2_dual_lights_test_v4351",
               "i1pro2_dual_lights_test_v4352")
    r = subprocess.run([cmake, "--build", str(build), "--target", *targets, "-j", jobs],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=1500)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    out = {}
    for t in targets:
        exe = next(p for p in build.rglob(t + "*")
                   if p.is_file() and os.access(p, os.X_OK) and p.name in (t, t + ".exe"))
        # budgeted for a loaded machine: about 15 s idle
        rr = subprocess.run([str(exe)], capture_output=True, text=True, encoding="utf-8",
                            timeout=600)
        assert rr.returncode == 0 and rr.stdout.rstrip().endswith("ALL DONE"), \
            t + " did not finish\n" + rr.stdout[-2000:] + rr.stderr[-2000:]
        out[t] = rr.stdout
    return out


def _lines(text: str, scn: str) -> "list[str]":
    return [ln.split(" ", 1)[1] for ln in text.splitlines() if ln.startswith(scn + " ")]


def _wire(text: str, scn: str) -> "list[str]":
    """The requests only (no timing, no notes)."""
    return [ln for ln in _lines(text, scn) if ln.split(" ", 1)[0] in ("CTL", "WR", "RD")]


def _blue_writes(wire: "list[str]") -> "list[int]":
    return [i for i, ln in enumerate(wire) if ln.startswith("WR 03 702 ")]


SAME = ("same_off_single", "same_off_dual", "same_lights_single", "same_lights_dual",
        "same_ready_dual")


@pytest.mark.parametrize("scn", SAME)
def test_every_life_that_asks_for_nothing_new_is_4_3_51s_wire(traces, scn):
    new = traces["i1pro2_dual_lights_test"]
    old = traces["i1pro2_dual_lights_test_v4351"]
    steps = [ln for ln in _lines(new, scn) if not ln.startswith("GAPMS")]
    assert steps == [ln for ln in _lines(old, scn) if not ln.startswith("GAPMS")]
    assert len(_wire(new, scn)) >= 2
    assert not _blue_writes(_wire(new, scn))


def test_the_blue_is_the_recorded_bytes_in_the_recorded_request(traces):
    wire = _wire(traces["i1pro2_dual_lights_test"], "blue_sent")
    (i,) = _blue_writes(wire)
    assert wire[i - 1] == "CTL d6 000002be"          # 0xD6 announcing 702 bytes, as recorded
    data = bytes.fromhex(wire[i].split()[3])
    assert len(data) == 702 and hashlib.sha256(data).hexdigest() == BLUE_SHA256


def test_the_blue_comes_after_the_lamp_pass_and_before_the_return_pass(traces):
    lines = _lines(traces["i1pro2_dual_lights_test"], "blue_sent")
    wire = [ln for ln in lines if ln.split(" ", 1)[0] in ("CTL", "WR", "RD", "STEP")]
    blue = next(k for k, ln in enumerate(wire) if ln.startswith("WR 03 702 "))
    lamp = max(k for k, ln in enumerate(wire[:blue]) if ln.startswith("CTL d4 ") and ln.endswith("0105"))
    after = [ln for ln in wire[blue + 1:] if ln.startswith("CTL d4 ")]
    # nothing but readings between the lamp pass and the blue; then the
    # return pass's dark trigger and its UV trigger "ruler end" (0x0209)
    between = [ln for ln in wire[lamp + 1:blue - 1] if not ln.startswith(("RD ", "STEP "))]
    assert between == []
    assert after[0].endswith("0000") and after[1].endswith("0209")
    assert wire.index("STEP return-wait") < blue < wire.index("STEP return-pass")


def test_nothing_else_on_the_wire_changes_with_the_blue(traces):
    t = traces["i1pro2_dual_lights_test"]
    wire = _wire(t, "blue_sent")
    (i,) = _blue_writes(wire)
    assert wire[:i - 1] + wire[i + 1:] == _wire(t, "same_lights_dual")


@pytest.mark.parametrize("scn,same", [
    ("blue_pressed_first", "same_lights_dual"),   # the button came first: skipped
    ("blue_no_signals", "same_ready_dual"),       # "ready light only": never
    ("blue_lights_off", "same_off_dual"),         # the lights Beta off: never
    ("blue_in_lamp_pass", "same_lights_dual"),    # in the lamp pass's wait: never
])
def test_where_the_blue_is_refused_nothing_is_sent(traces, scn, same):
    t = traces["i1pro2_dual_lights_test"]
    assert _wire(t, scn) == _wire(t, same)
    assert all(ln == "SECOND-PASS 0" for ln in _lines(t, scn) if ln.startswith("SECOND-PASS"))


def test_never_in_a_single_scan(traces):
    t = traces["i1pro2_dual_lights_test"]
    assert _wire(t, "blue_single_scan") == _wire(t, "same_lights_single")


def test_once_per_return_pass_and_never_after_its_wait(traces):
    t = traces["i1pro2_dual_lights_test"]
    assert [ln for ln in _lines(t, "blue_twice") if ln.startswith("SECOND-PASS")] == \
        ["SECOND-PASS 1", "SECOND-PASS 0"]
    assert len(_blue_writes(_wire(t, "blue_twice"))) == 1
    # blue_sent asks again in the next strip's lamp pass and after the wait
    assert [ln for ln in _lines(t, "blue_sent") if ln.startswith("SECOND-PASS")] == \
        ["SECOND-PASS 1", "SECOND-PASS 0", "SECOND-PASS 0"]


def _gap_after(t: str, scn: str, step: str) -> int:
    """The gap before the first trigger after STEP *step*."""
    lines = _lines(t, scn)
    k = lines.index("STEP " + step)
    return int(next(ln for ln in lines[k:] if ln.startswith("GAPMS")).split()[1])


def _return_gap(t: str, scn: str) -> int:
    return _gap_after(t, scn, "return-pass")


def _held(t: str, scn: str) -> "list[tuple[int, int]]":
    return [(int(a), int(b)) for a, b in
            (ln.split()[1:3] for ln in _lines(t, scn) if ln.startswith("HELD "))]


def test_the_quiet_time_changes_the_wait_and_never_a_byte(traces):
    """The lamp pass's first trigger comes after the open's light write: it
    waits the user's quiet time (none, 400 ms, out of range = 2100 ms)."""
    t = traces["i1pro2_dual_lights_test"]
    for scn in ("quiet_0", "quiet_400", "quiet_bad", "quiet_default"):
        assert _wire(t, scn) == _wire(t, "blue_sent"), scn
    assert _gap_after(t, "quiet_0", "lamp-pass") < 150           # no wait at all
    assert 400 <= _gap_after(t, "quiet_400", "lamp-pass") < 1500
    assert _gap_after(t, "quiet_bad", "lamp-pass") >= 2100       # out of range: 4.3.37's 2100 ms
    assert _gap_after(t, "quiet_default", "lamp-pass") >= 2100   # never set: 2100 ms


@pytest.mark.parametrize("scn", ["quiet_0", "quiet_400", "quiet_bad", "quiet_default"])
def test_after_the_blue_the_wait_is_the_blues_own_370_ms(traces, scn):
    """4.3.52 fix round: i1Profiler triggered the return pass 0.37-1.39 s after
    the blue (15 of 15). After the blue alone ChromIQ waits 370 ms, whatever
    the user's quiet time: never closer (quiet 0), never the default 2.1 s."""
    t = traces["i1pro2_dual_lights_test"]
    gap = _return_gap(t, scn)
    assert 370 <= gap < 1500, gap                  # < 2100: not the default; >= 370: the floor
    # the hold before the return pass is said as "after the blue"; every other
    # hold is not
    holds = _held(t, scn)
    assert [b for _ms, b in holds].count(1) == 1, holds
    lines = _lines(t, scn)
    k = lines.index("STEP return-pass")
    assert next(ln for ln in lines[k:] if ln.startswith("HELD ")).endswith(" 1")


def test_a_write_after_the_blue_gives_the_users_quiet_time_back(traces):
    """The blue showing, the return pass left, a calibration: it starts dark
    (OFF_SLOW, as always) and the wait after that write is the user's
    (1000 ms here), not the blue's 370."""
    t = traces["i1pro2_dual_lights_test"]
    wire = _wire(t, "blue_then_calibration")
    (b,) = _blue_writes(wire)
    assert wire[b + 1:b + 3] == ["CTL d6 00000012", "WR 03 18 000000010000000a00000002003640000001"]
    assert _gap_after(t, "blue_then_calibration", "calibration") >= 1000
    assert [a for _ms, a in _held(t, "blue_then_calibration")] == [0, 0]


@pytest.mark.parametrize("scn", ["user_wait_single", "user_wait_ready_dual"])
def test_without_the_blue_every_trigger_waits_the_users_quiet_time(traces, scn):
    """4.3.52 release (re-review S1): the dual scan off, or "ready light only" (no blue): every
    trigger after a light write waits the user's 1000 ms, and no hold is counted from the
    blue. MUTATION, proven red: the blue's floor applied with the dual scan off."""
    t = traces["i1pro2_dual_lights_test"]
    gaps = [int(ln.split()[1]) for ln in _lines(t, scn) if ln.startswith("GAPMS")]
    assert gaps and all(g >= 1000 for g in gaps), gaps
    assert all(b == 0 for _ms, b in _held(t, scn)), _held(t, scn)
    assert not _blue_writes(_wire(t, scn))


def test_after_an_esc_in_the_second_pass_the_next_strip_waits_the_users_quiet_time(traces):
    """4.3.52 release (re-review S2): the blue showing, the return pass left (Esc), the next
    strip's FIRST pass: the user's 1000 ms, not the blue's 370 (the help says the 0.37 s is
    "before the second pass can start"). Red before: 377 ms."""
    t = traces["i1pro2_dual_lights_test"]
    assert len(_blue_writes(_wire(t, "esc_then_next_lamp"))) == 1
    assert _gap_after(t, "esc_then_next_lamp", "esc-then-lamp") >= 1000
    lines = _lines(t, "esc_then_next_lamp")
    k = lines.index("STEP esc-then-lamp")
    assert all(ln.endswith(" 0") for ln in lines[k:] if ln.startswith("HELD "))


def test_a_result_after_the_blue_gives_the_users_quiet_time_back(traces):
    t = traces["i1pro2_dual_lights_test"]
    assert _return_gap(t, "blue_then_result") >= 1000
    assert all(b == 0 for _ms, b in _held(t, "blue_then_result"))


# ---------------------------------------------------------------------------
# The driver block (native/instlib/i1pro_imp.c, via scripts/vendor_instlib.py)
# ---------------------------------------------------------------------------
def _driver() -> str:
    return (INSTLIB / "i1pro_imp.c").read_text(encoding="utf-8", errors="surrogateescape")


def _body(text: str, head: str) -> str:
    b = text[text.index(head):]
    return b[:b.index("\n}\n")]


def test_the_default_quiet_time_is_still_2100_ms():
    t = _driver()
    assert "#define CQ_LIGHTS_QUIET_MS   2100" in t
    assert "int i1pro2_cq_lights_quiet_ms = -1;" in t
    q = _body(t, "static int cq_lights_quiet_now(i1proimp *m) {")
    assert ("(i1pro2_cq_lights_quiet_ms >= 0 && i1pro2_cq_lights_quiet_ms <= CQ_LIGHTS_QUIET_MAX_MS)"
            in q)
    assert q.rstrip().endswith("return CQ_LIGHTS_QUIET_MS;")
    assert "#define CQ_LIGHTS_QUIET_MAX_MS 10000" in t
    # asked again at every turn of the hold: an off carried out during it ends
    # the blue's own quiet time
    loop = _body(t, "static void cq_lights_quiet(i1proimp *m) {")
    assert loop.index("for (;;) {") < loop.index("quiet = cq_lights_quiet_now(m);")


def test_the_blues_own_quiet_time_is_the_vendors_shortest_gap():
    """One number, in the driver; the app's help quotes the same recorded value."""
    from core import i1pro2_lights_quiet as lq
    t = _driver()
    assert "#define CQ_LIGHTS_BLUE_QUIET_MS 370\n" in t
    assert round(lq.RECORDED_HAND_MIN_S * 1000) == 370 == lq.BLUE_QUIET_MS
    q = _body(t, "static int cq_lights_quiet_now(i1proimp *m) {")
    # the tests' own first, then the blue's, then the user's
    assert (q.index("i1pro2_cq_lights_quiet_ms_for_test > 0")
            < q.index("if (cq_lights_last_was_blue(m))")
            < q.index(": CQ_LIGHTS_BLUE_QUIET_MS;")     # 4.3.53: unless the helper passed one
            < q.index("i1pro2_cq_lights_quiet_ms >= 0"))
    blue = _body(t, "static int cq_lights_last_was_blue(i1proimp *m) {")
    # 4.3.53: either side's blue (the side follows pass 1's direction)
    assert "m->cq_lights == CQ_LIGHTS_LIT && CQ_LIGHTS_IS_BLUE(m->cq_lights_prog)" in blue
    # 4.3.52 release (re-review S2): only while that strip's return pass is the one waiting
    assert "i1pro2_cq_dual_phase(m->p) == CQ_DUAL_PHASE_UV" in blue
    # and the simulator holds the same number
    sim = (ROOT / "tests" / "helpers" / "dual_sim_helper.py").read_text(encoding="utf-8")
    assert "\nBLUE_QUIET_MS = 370\n" in sim


def test_the_blue_entry_checks_everything_before_it_sends():
    b = _body(_driver(), "int i1pro2_cq_lights_second_pass(void *pp) {")
    send = b.index("cq_lights_send(p, which")
    guard = b[:send]
    for need in ("cq_lights_m(p)", "!m->cq_lights_signals", "!m->cq_lights_reading",
                 "cq_lights_trigger_pending(m)", "cq_lights_pressed(m)",
                 "i1pro2_cq_dual_phase(pp) != CQ_DUAL_PHASE_UV",
                 "!i1pro2_cq_dual_uv_pass_ready(pp)",
                 "CQ_LIGHTS_IS_BLUE(m->cq_lights_prog)"):
        assert need in guard, need
    assert b.count("cq_lights_send(") == 1


def test_the_vendor_script_holds_the_same_block():
    script = (ROOT / "scripts" / "vendor_instlib.py").read_text(encoding="utf-8")
    for s in ("int i1pro2_cq_lights_second_pass(void *pp) {", "int i1pro2_cq_lights_quiet_ms = -1;",
              "#define CQ_LIGHTS_BLUE     7"):
        assert s in script and s in _driver()


# ---------------------------------------------------------------------------
# The helper (native/chartread_helper)
# ---------------------------------------------------------------------------
def _helper() -> str:
    return (HELPER_SRC / "chromiq_chartread.c").read_text(encoding="utf-8",
                                                          errors="surrogateescape")


def test_the_helper_sends_the_blue_550_ms_after_pass_1_from_the_armed_wait():
    h = _helper()
    assert "#define CQ_LIGHTS_BLUE_AFTER_MS 550" in h
    due = _body(h, "static void cq_lights_second_pass_due(void) {")
    assert "cq_lights_signals_on()" in due and "cq_lights_gen != 2" in due
    assert "i1pro2_cq_" not in due                  # only a time, nothing sent
    poll = _body(h, "static void cq_lights_second_pass_poll(void) {")
    assert "i1pro2_cq_lights_second_pass(cq_lights_it)" in poll
    assert poll.index("cq_lights_blue_due = 0;") < poll.index("i1pro2_cq_lights_second_pass(")
    over = _body(h, "static void cq_lights_second_pass_over(void) {")
    assert "i1pro2_cq_" not in over and '\\"why\\":\\"early\\"' in over
    # from the armed wait only, where no key is waiting
    k = h.index("cq_lights_second_pass_poll();\t/* 4.3.52")
    assert "if (purp == inst_armed && c == CQ_KEY_NONE)" in h[k - 80:k]


_BLUE_HARNESS = r"""
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
typedef struct _inst inst;
static unsigned int now_ms = 5000;
static unsigned int msec_time(void) { return now_ms; }
static inst *cq_lights_it = (inst *)1;
static int cq_lights_gen = 2;
static int sig_on = 1;
static int cq_lights_signals_on(void) { return sig_on; }
static int i1pro2_cq_lights_second_pass(void *pp) { (void)pp; printf("SEND\n"); return 1; }
static void cq_emit_raw(const char *fmt, ...) {
	va_list a; va_start(a, fmt); vprintf(fmt, a); va_end(a); printf("\n");
}
@@SOURCE@@
static void step(const char *s) { printf("STEP %s\n", s); }
int main(void) {
	/* sent once it is due, never before, never twice */
	step("due"); cq_lights_second_pass_due();
	now_ms += 100; cq_lights_second_pass_poll();
	now_ms += 500; cq_lights_second_pass_poll();
	now_ms += 100; cq_lights_second_pass_poll();
	cq_lights_second_pass_over();
	/* left before it was due: said once, and never sent later */
	step("early"); cq_lights_second_pass_due();
	now_ms += 100; cq_lights_second_pass_over();
	now_ms += 5000; cq_lights_second_pass_poll();
	step("next"); now_ms += 5000; cq_lights_second_pass_poll(); cq_lights_second_pass_over();
	/* without result signals, or on an i1Pro 3: never due */
	step("nosig"); sig_on = 0; cq_lights_second_pass_due(); sig_on = 1;
	now_ms += 1000; cq_lights_second_pass_poll(); cq_lights_second_pass_over();
	step("gen3"); cq_lights_gen = 3; cq_lights_second_pass_due(); cq_lights_gen = 2;
	now_ms += 1000; cq_lights_second_pass_poll(); cq_lights_second_pass_over();
	printf("END\n");
	return 0;
}
"""


def test_the_helpers_due_poll_over_run_as_written(tmp_path):
    """Review S3 (fix round): the helper's three blue functions, compiled from
    the SHIPPED source text with stubs around them, and run. A return pass
    left before the blue was due must clear the due time, so nothing is sent
    later (a missing clear in cq_lights_second_pass_over turned no test red)."""
    cc = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
    if cc is None or sys.platform == "win32":
        pytest.skip("no C compiler here")
    h = _helper()
    a = h.index("#define CQ_LIGHTS_BLUE_AFTER_MS 550")
    k = h.index("static void cq_lights_second_pass_over(void) {")
    src = h[a:h.index("\n}\n", k) + 3]
    c = tmp_path / "blue_harness.c"
    c.write_text(_BLUE_HARNESS.replace("@@SOURCE@@", src), encoding="utf-8")
    exe = tmp_path / "blue_harness"
    r = subprocess.run([cc, "-std=c99", "-Wall", "-o", str(exe), str(c)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, r.stderr
    out = subprocess.run([str(exe)], capture_output=True, text=True, encoding="utf-8",
                         timeout=60).stdout.split("\n")
    assert out[:-1] == [
        "STEP due", "SEND",
        "STEP early", '{"event":"lights","second_pass":"skipped","why":"early"}',
        "STEP next",
        "STEP nosig",
        "STEP gen3",
        "END"], out


def test_the_dual_strip_sets_the_blue_due_only_where_pass_2_is_asked_for():
    d = (HELPER_SRC / "chromiq_dualdev.c").read_text(encoding="utf-8")
    body = d[d.index("static void cq_dd_strip("):]
    ready = body.index("if (!i1pro2_cq_dual_uv_pass_ready(it)) {")
    ask = body.index('"{\\"event\\":\\"dual_pass\\"')
    due = body.index("cq_lights_second_pass_due();")
    loop = body.index("rv2 = it->read_strip(it, \"STRIP\"")
    over = body.index("cq_lights_second_pass_over();")
    assert ready < ask < due < loop < over
    assert body.count("cq_lights_second_pass_due();") == 1


def test_the_quiet_flag_takes_only_a_whole_number_from_0_to_10000():
    h = _helper()
    k = h.index('strcmp(argv[ai], "--lights-quiet-ms") == 0')
    block = h[k:k + 900]
    assert "strtol(argv[ai + 1], &end, 10)" in block
    assert "*end == '\\0'" in block and "v >= 0 && v <= 10000" in block
    assert "eat = 2;" in block
    s = h.index("i1pro2_cq_lights_quiet_ms = cq_lights_quiet_ms;")
    assert s < h.index("if (!(cq_lights_gen == 3 ? i1pro3_cq_lights_begin(it)", s)


def test_the_helper_names_the_new_abilities_and_build():
    h = _helper()
    assert '\\"lights_quiet\\",\\"i1pro2_dual_blue\\"' in h
    ext = (HELPER_SRC / "chromiq_ext.h").read_text(encoding="utf-8")
    # 4.3.53: 2026-11-20d = 20c + the waits as values (tests/test_instrument_waits.py)
    assert '"chromiq-chartread 2026-11-20e ' in ext
    assert "+conditions-kept+lights-quiet+i1pro2-dual-blue+blue-own-quiet+blue-quiet-return-only" in ext


def test_the_helper_says_a_hold_after_the_blue_and_both_numbers_from_the_driver():
    h = _helper()
    held = _body(h, "static void cq_lights_held2(int ms) {")
    assert "if (i1pro2_cq_lights_held_after_blue)" in held
    assert '\\"after\\":\\"blue\\"' in held and "i1pro2_cq_lights_blue_quiet_ms" in held
    s = h[h.index('"\\"during_reading\\":\\"%s\\",\\"firmware\\":%d,\\"quiet_ms\\":%d,"'):]
    s = s[:s.index("else")]
    assert "i1pro2_cq_lights_quiet_default_ms" in s and "i1pro2_cq_lights_blue_quiet_ms" in s
    assert "2100" not in s


def test_the_bundled_helper_is_this_build():
    exe = ROOT / "native" / "chromiq-chartread"
    if not exe.is_file():
        pytest.skip("no bundled helper in this checkout")
    data = exe.read_bytes()
    assert b"chromiq-chartread 2026-11-20e " in data
    assert b'"why\\":\\"early\\"' in data or b'"why":"early"' in data
    assert b"blue_quiet_ms" in data and b'"after":"blue"' in data


# ---------------------------------------------------------------------------
# The app: the setting, the command line, the log
# ---------------------------------------------------------------------------
def test_the_setting_default_and_range():
    from core.settings import DEFAULTS
    from core import i1pro2_lights_quiet as lq
    assert DEFAULTS["i1pro2_lights_quiet_s"] == 2.1 == lq.DEFAULT_S
    assert (lq.MIN_S, lq.MAX_S, lq.DEFAULT_MS) == (0.0, 10.0, 2100)
    assert lq.to_ms(2.1) == 2100 and lq.to_ms(0) == 0 and lq.to_ms(0.4) == 400
    assert lq.to_ms(10) == 10000
    for bad in (-0.1, 10.1, "x", None, float("nan")):
        assert lq.to_ms(bad) == 2100, bad


def test_the_session_header_names_the_setting():
    from core.beta_registry import BETA_SUB_OPTIONS, LOGGED_KEYS
    assert "i1pro2_lights_quiet_s" in BETA_SUB_OPTIONS
    assert "i1pro2_lights_quiet_s" in LOGGED_KEYS


class _Runner:
    def __init__(self):
        self.calls = []
        self.is_running = False

    def run(self, tool, args, cwd, on_line=None, on_finish=None, use_pty=False):
        self.calls.append((str(tool), list(args)))

    def set_kill_courtesy(self, line):
        pass

    def write_stdin(self, text):
        pass


CAPS = {"i1pro2_lights", "lights_signals", "lights_during_reading", "lights_quiet"}


def _args(tmp_path, monkeypatch, *, lights=True, quiet=2.1, caps=CAPS):
    from workflow import chartread_engine
    from workflow.measure_manager import MeasureManager, MeasureParams
    monkeypatch.setattr(chartread_engine, "helper_caps", lambda helper=None: frozenset(caps))
    monkeypatch.setattr(MeasureManager, "_refuse_system_port", lambda self, *a, **k: False)
    runner = _Runner()
    m = MeasureManager(runner)
    p = MeasureParams(ti1_path=tmp_path / "chart.ti1",
                      engine_helper=tmp_path / "chromiq-chartread",
                      engine_i1pro2_lights=lights, engine_lights_signals=True,
                      engine_lights_quiet_s=quiet)
    m.start(p, lambda _l: None, lambda _c: None)
    return runner.calls[-1][1], m


def test_the_default_keeps_the_command_line(qapp, tmp_path, monkeypatch):
    args, _m = _args(tmp_path, monkeypatch, quiet=2.1)
    assert "--i1pro2-lights" in args and "--lights-quiet-ms" not in args
    off, _m = _args(tmp_path, monkeypatch, lights=False, quiet=0.0)
    assert "--lights-quiet-ms" not in off and "--i1pro2-lights" not in off


@pytest.mark.parametrize("quiet,ms", [(0.0, "0"), (0.4, "400"), (10.0, "10000")])
def test_another_value_is_passed_in_ms(qapp, tmp_path, monkeypatch, quiet, ms):
    base, _m = _args(tmp_path, monkeypatch, quiet=2.1)
    args, m = _args(tmp_path, monkeypatch, quiet=quiet)
    k = args.index("--lights-quiet-ms")
    assert args[k + 1] == ms
    assert args[:k] + args[k + 2:] == base
    assert m._lights_quiet_ms == int(ms)


def test_a_helper_without_the_flag_is_not_given_it(qapp, tmp_path, monkeypatch):
    args, m = _args(tmp_path, monkeypatch, quiet=0.4, caps=CAPS - {"lights_quiet"})
    assert "--lights-quiet-ms" not in args and m._lights_quiet_ms == 2100


def test_the_start_line_names_the_quiet_time():
    src = (ROOT / "workflow" / "measure_log.py").read_text(encoding="utf-8")
    assert "i1pro2_lights_quiet_s=lights_quiet_s," in src
    mm = (ROOT / "workflow" / "measure_manager.py").read_text(encoding="utf-8")
    assert "lights_quiet_s=(getattr(self, \"_lights_quiet_ms\"" in mm


def test_the_start_line_is_written_with_it(caplog, tmp_path):
    from types import SimpleNamespace
    from workflow.measure_log import log_start
    p = SimpleNamespace(ti1_path=tmp_path / "c.ti1", patch_by_patch=False, extra_args=[],
                        instrument=1, high_res=False, resume=False)
    with caplog.at_level("INFO"):
        log_start(p, reader="engine", lights=True, lights_quiet_s=0.4)
    assert any("measure start:" in r.getMessage() and " i1pro2_lights_quiet_s=0.4" in r.getMessage()
               for r in caplog.records)


def test_an_i1pro3_session_says_it_uses_no_quiet_time(qapp, caplog):
    """Review S7: the i1Pro 3 has no quiet time; its session says so."""
    with caplog.at_level("INFO"):
        _events(qapp, [{"event": "lights", "active": True, "instrument": "i1pro3",
                        "signals": True, "during_reading": "off", "firmware": 101,
                        "quiet_ms": -1, "blue_quiet_ms": -1}])
    msgs = [r.getMessage() for r in caplog.records]
    assert any("lights: instrument=i1pro3 quiet=not_used" in m for m in msgs)
    assert not any("instrument=i1pro3 quiet_ms" in m for m in msgs)


def _events(qapp, evs, quiet_ms=2100):
    from workflow.measure_manager import MeasureManager
    m = MeasureManager(_Runner())
    m._lights_quiet_ms = quiet_ms
    m._lights_held_said = False
    m._lights_option = True
    out = []
    for ev in evs:
        m._on_lights_event(ev, out.append)
    return out


def test_the_blue_is_said_in_the_measure_log_and_the_app_log(qapp, caplog):
    with caplog.at_level("INFO"):
        out = _events(qapp, [{"event": "lights", "sent": "blue"}])
    assert out == ["[Engine] Instrument lights (beta): blue. The second pass of this strip is due."]
    assert any("lights: sent=blue" in r.getMessage() and "second_pass_due" in r.getMessage()
               for r in caplog.records)


def test_a_skipped_blue_goes_to_the_app_log_only(qapp, caplog):
    with caplog.at_level("INFO"):
        out = _events(qapp, [{"event": "lights", "second_pass": "skipped", "why": "early"}])
    assert out == []
    assert any("second_pass=skipped" in r.getMessage() and "why=early" in r.getMessage()
               for r in caplog.records)


def test_a_hold_after_the_blue_goes_to_the_app_log_only(qapp, caplog):
    """Fix round: the return pass's hold after the blue is the blue's own
    370 ms, not the user's quiet time: the once-per-session Measure-log line
    (which names the user's wait) is kept for a real hold."""
    from workflow.measure_manager import MeasureManager
    m = MeasureManager(_Runner())
    m._lights_quiet_ms, m._lights_held_said, m._lights_option = 2100, False, True
    out = []
    with caplog.at_level("INFO"):
        m._on_lights_event({"event": "lights", "held_ms": 250, "after": "blue",
                            "quiet_ms": 370}, out.append)
    assert out == [] and m._lights_held_said is False
    assert any("lights: held_ms=250 after=blue quiet_ms=370" in r.getMessage()
               for r in caplog.records)
    m._on_lights_event({"event": "lights", "held_ms": 1500}, out.append)
    assert len(out) == 1 and "about two seconds" in out[0]


def test_the_wait_is_said_with_the_users_value(qapp):
    out = _events(qapp, [{"event": "lights", "held_ms": 300}], quiet_ms=400)
    assert len(out) == 1 and "0.4 s" in out[0] and "Preferences > Beta" in out[0]
    default = _events(qapp, [{"event": "lights", "held_ms": 300}])
    assert "about two seconds" in default[0]


def test_the_session_line_says_the_quiet_time_in_use(qapp, caplog):
    with caplog.at_level("INFO"):
        _events(qapp, [{"event": "lights", "active": True, "instrument": "i1pro2",
                        "signals": True, "during_reading": "off", "firmware": 634,
                        "quiet_ms": 400}])
    assert any("lights: instrument=i1pro2 quiet_ms=400 quiet_default=off" in r.getMessage()
               for r in caplog.records)


@pytest.fixture
def dialog(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat)
    dlg = SettingsDialog(s)
    yield dlg, s
    dlg.deleteLater()


def test_preferences_greys_the_wait_until_the_lights_are_on(dialog):
    dlg, _s = dialog
    assert dlg._lights_quiet_spin.isEnabled() is False
    assert dlg._lights_quiet_spin.value() == pytest.approx(2.1)
    assert (dlg._lights_quiet_spin.minimum(), dlg._lights_quiet_spin.maximum()) == (0.0, 10.0)
    dlg._i1pro2_lights_check.setChecked(True)
    assert dlg._lights_quiet_spin.isEnabled() is True
    assert dlg._lights_quiet_label.buddy() is dlg._lights_quiet_spin


def test_preferences_saves_the_wait(dialog):
    dlg, s = dialog
    dlg._i1pro2_lights_check.setChecked(True)
    dlg._lights_quiet_spin.setValue(0.4)
    dlg._save_and_close()
    assert s.get("i1pro2_lights_quiet_s") == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# The field (fix round, review S2): two decimals, both marks, the app's mark,
# never a silent snap back, and the value reaches the helper exactly
# ---------------------------------------------------------------------------
def _type(spin, text):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    le = spin.lineEdit()
    spin.setFocus()
    le.selectAll()
    QTest.keyClick(le, Qt.Key.Key_Delete)
    QTest.keyClicks(le, text)
    QTest.keyClick(le, Qt.Key.Key_Return)


@pytest.fixture
def german():
    from core import i18n
    i18n.set_language("de")
    yield
    i18n.set_language(i18n.SOURCE_LANGUAGE)


def test_the_field_has_two_decimals_and_steps_of_0_05(dialog):
    dlg, _s = dialog
    spin = dlg._lights_quiet_spin
    assert spin.decimals() == 2 and spin.singleStep() == pytest.approx(0.05)
    dlg._i1pro2_lights_check.setChecked(True)
    spin.setValue(0.37)
    assert spin.value() == pytest.approx(0.37)          # not 0.4 any more
    spin.stepBy(1)
    assert spin.value() == pytest.approx(0.42)


@pytest.mark.parametrize("typed", ["0,37", "0.37"])
def test_both_marks_are_taken_in_english_and_shown_with_a_point(dialog, typed):
    dlg, _s = dialog
    dlg._i1pro2_lights_check.setChecked(True)
    spin = dlg._lights_quiet_spin
    spin.show()
    _type(spin, typed)
    assert spin.value() == pytest.approx(0.37)
    assert spin.text() == "0.37 s"
    assert dlg._lights_quiet_back.isHidden()


@pytest.mark.parametrize("typed", ["0,37", "0.37"])
def test_both_marks_are_taken_in_german_and_shown_with_a_comma(german, qapp, tmp_path, typed):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat)
    dlg = SettingsDialog(s)
    try:
        dlg._i1pro2_lights_check.setChecked(True)
        spin = dlg._lights_quiet_spin
        spin.show()
        assert spin.text() == "2,10 s"
        _type(spin, typed)
        assert spin.value() == pytest.approx(0.37)
        assert spin.text() == "0,37 s"
    finally:
        dlg.deleteLater()


def test_a_value_that_cannot_be_taken_is_said_not_silently_undone(dialog):
    dlg, _s = dialog
    dlg._i1pro2_lights_check.setChecked(True)
    spin = dlg._lights_quiet_spin
    spin.show()
    spin.setValue(0.46)
    _type(spin, "")                                      # an empty field
    spin.editingFinished.emit()
    assert spin.value() == pytest.approx(0.46)
    back = dlg._lights_quiet_back
    assert not back.isHidden()
    assert back.text() == "This is not a number from 0 to 10 s, so the wait stays at 0.46 s."
    _type(spin, "0.5")                                   # a good one hides it again
    assert back.isHidden() and spin.value() == pytest.approx(0.5)


@pytest.mark.parametrize("typed,ms", [("0.05", 50), ("0.37", 370), ("0.46", 460),
                                      ("2.1", 2100), ("10", 10000)])
def test_the_typed_value_reaches_the_helper_exactly(dialog, tmp_path, monkeypatch, caplog,
                                                    typed, ms):
    """Typed in Preferences -> stored -> the Measure tab's parameters ->
    --lights-quiet-ms -> the app log, with no rounding on the way."""
    dlg, s = dialog
    dlg._i1pro2_lights_check.setChecked(True)
    spin = dlg._lights_quiet_spin
    spin.show()
    _type(spin, typed)
    dlg._save_and_close()
    stored = s.get("i1pro2_lights_quiet_s")
    from core import i1pro2_lights_quiet as lq
    assert lq.to_ms(stored) == ms
    args, m = _args(tmp_path, monkeypatch, quiet=stored)
    if ms == 2100:
        assert "--lights-quiet-ms" not in args          # the default: 4.3.51's line
    else:
        assert args[args.index("--lights-quiet-ms") + 1] == str(ms)
    assert m._lights_quiet_ms == ms
    with caplog.at_level("INFO"):
        _events(None, [{"event": "lights", "active": True, "instrument": "i1pro2",
                        "signals": True, "during_reading": "off", "firmware": 634,
                        "quiet_ms": ms, "blue_quiet_ms": 370}])
    assert any(f"lights: instrument=i1pro2 quiet_ms={ms} " in r.getMessage()
               for r in caplog.records)


@pytest.mark.parametrize("stored", [0.37, 0.05, 10.0, 2.1])
def test_the_measure_tab_passes_the_setting_not_a_fixed_value(qapp, tmp_path, monkeypatch,
                                                             stored):
    """Review S3 (fix round): Preferences -> Start. The Measure tab builds the
    parameters from the setting; a fixed 2.1 there turned no test red."""
    from core.settings import DEFAULTS
    from workflow import chartread_engine
    from workflow.measure_manager import MeasureParams
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure

    class _S:
        def __init__(self):
            self._d = dict(DEFAULTS, i1pro2_lights_beta=True, i1pro2_lights_quiet_s=stored)

        def get(self, key, default=None):
            return self._d.get(key, default)

        def set(self, key, value):
            self._d[key] = value

    s = _S()
    tab = TabMeasure(ArgyllRunner(s), s)
    try:
        monkeypatch.setattr(tab, "_engine_selected", lambda: True)
        monkeypatch.setattr(chartread_engine, "helper_path",
                            lambda: tmp_path / "chromiq-chartread")
        p = tab._apply_engine_params(MeasureParams(ti1_path=tmp_path / "c.ti1"))
        assert p.engine_i1pro2_lights is True
        assert p.engine_lights_quiet_s == pytest.approx(stored)
    finally:
        tab.close()


def test_the_help_names_the_recorded_numbers_and_the_risk():
    from ui.dialogs.settings_dialog import (i1pro2_lights_help, i1pro2_lights_quiet_help,
                                            i1pro2_lights_quiet_note)
    note = i1pro2_lights_quiet_note()
    assert "2.1 s" in note and "0.37 s" in note and "0.46 s" in note and "app log" in note
    assert "a measurement can even end" in note                  # fix round, M2
    h = i1pro2_lights_quiet_help()
    for need in ("0.37", "0.46", "0.01", "lost communication", "M1 and M2", "0 to 10 s",
                 "app log"):
        assert need in h, need
    # fix round M2: the worst case is said, and "nothing worse" is gone
    assert "If it keeps failing, the measurement ends, and you must start it again" in h
    assert "Continue Measurement keeps the strips you already read" in h
    assert "you must read the strip again" in h
    assert "Nothing worse is known" not in h
    # fix round S4: the wait is a change in ChromIQ's copy of the instrument code
    assert ("**This changes how ChromIQ talks to the instrument:** the wait is in ChromIQ's "
            "copy of ArgyllCMS's instrument code.") in h
    # fix round, item 4: the blue's own wait, said in both places (4.3.53:
    # its own field, named by its label)
    assert ("after the blue light of a dual scan, ChromIQ waits the time set below in "
            "“Dual scan, wait after the blue light”") in h
    lights = i1pro2_lights_help()
    assert "second pass of this strip is due" in lights
    assert "changes how ChromIQ talks to the instrument" in lights
    # 4.3.53 (the tester Nelson): the side the second pass moves towards
    assert "The blue light blinks on the side the second pass should move towards" in lights
    assert "on the right after a first pass from right to left" in lights
    assert "either direction" in lights
    assert ("After the blue light, ChromIQ waits the time set below in “Dual scan, wait "
            "after the blue light” (default 0.37 s) before the second pass can start.") in lights
    assert "keep the instrument still until it beeps, then slide" in lights


def test_the_german_help_says_the_same_and_plainly():
    """N5 (review): "ist dran" was colloquial; and the German text carries the
    new sentences (the catalogue test checks every language has the keys)."""
    import json
    de = json.loads((ROOT / "data" / "i18n" / "de.json").read_text(encoding="utf-8"))
    vals = "\n".join(v for v in de.values() if isinstance(v, str))
    assert "ist dran" not in vals
    assert "Der zweite Durchgang dieses Streifens ist jetzt an der Reihe." in vals
    assert "Schlägt sie immer wieder fehl, endet die Messung" in vals


# ---------------------------------------------------------------------------
# 4.3.53: the waits as values the helper passes (core/instrument_waits.py);
# the same fake USB, against 4.3.52's driver too. The app side is in
# tests/test_instrument_waits.py.
# ---------------------------------------------------------------------------
#: the real minimum waits of the 4.3.52 lives (ms): the blue's, the user's
#: 1000, ArgyllCMS's lamp wait, the default quiet time
_FLOORS = (0, 370, 1000, 1500, 2100)


def _floor(ms: int) -> int:
    """The longest real minimum wait a measured gap satisfies."""
    return max(f for f in _FLOORS if f <= ms + 5)


def _same_wait(a: int, b: int) -> bool:
    """Two gaps come from the same wait: they meet the same floor, or differ
    only by scheduling (a loaded machine makes a gap longer, never shorter)."""
    return _floor(a) == _floor(b) or abs(a - b) < 250


def _scenarios(text: str) -> "list[str]":
    seen = []
    for ln in text.splitlines():
        s = ln.split(" ", 1)[0]
        if s not in seen and s != "ALL":
            seen.append(s)
    return seen


def _timed(text: str, scn: str, what: str) -> "list[int]":
    return [int(ln.split()[1]) for ln in _lines(text, scn) if ln.startswith(what + " ")]


def test_4352_every_life_of_4_3_52_is_the_same_wire_and_the_same_waits(traces):
    """Nothing passed: the driver is 4.3.52's, request for request, and every
    trigger waits as long as there (a wait is a minimum: the gaps meet the
    same floors). The lamp life included: ArgyllCMS's own 1500 ms."""
    new = traces["i1pro2_dual_lights_test"]
    old = traces["i1pro2_dual_lights_test_v4352"]
    lives = _scenarios(old)
    assert "lamp_default" in lives and "quiet_default" in lives and len(lives) >= 20
    for scn in lives:
        assert _wire(new, scn) == _wire(old, scn), scn
        for what in ("GAPMS", "LAMPGAP"):
            a, b = _timed(new, scn, what), _timed(old, scn, what)
            assert len(a) == len(b), (scn, what)
            assert all(_same_wait(x, y) for x, y in zip(a, b)), (scn, what, a, b)
        assert [h[1] for h in _held(new, scn)] == [h[1] for h in _held(old, scn)], scn


@pytest.mark.parametrize("scn,low,high", [
    ("blue_wait_600", 600, 2100),     # passed: 600 ms, not the 2100 of the quiet time
    ("blue_wait_0", 0, 150),          # passed: no wait at all
    ("blue_wait_bad", 370, 2100),     # out of range: the compiled 370 ms
    ("blue_wait_370", 370, 2100),     # passed at the default: as 4.3.52
])
def test_4353_the_blue_wait_passed_changes_only_that_wait(traces, scn, low, high):
    t = traces["i1pro2_dual_lights_test"]
    assert _wire(t, scn) == _wire(t, "quiet_default"), scn       # not a byte more or less
    gap = _return_gap(t, scn)
    assert low <= gap < high, gap
    # every other trigger keeps the quiet time (2100 ms, never set)
    lines = _lines(t, scn)
    k = lines.index("STEP return-pass")
    gaps = [i for i, ln in enumerate(lines) if ln.startswith("GAPMS")]
    ret = [i for i in gaps if i > k][:2]           # the return pass's two triggers
    others = [int(lines[i].split()[1]) for i in gaps if i not in ret]
    assert len(others) == 4 and all(g >= 2100 for g in others), others


@pytest.mark.parametrize("scn,low,high", [
    ("lamp_300", 300, 1500),          # passed: 300 ms
    ("lamp_0", 0, 300),               # passed: no wait
    ("lamp_bad", 1500, 10 ** 6),      # out of range: ArgyllCMS's 1500 ms
    ("lamp_1500", 1500, 10 ** 6),     # passed at the default
    ("lamp_default", 1500, 10 ** 6),  # nothing passed: ArgyllCMS's 1500 ms
])
def test_4353_the_lamp_wait_passed_changes_only_that_wait(traces, scn, low, high):
    t = traces["i1pro2_dual_lights_test"]
    assert _wire(t, scn) == _wire(t, "lamp_default"), scn
    gaps = _timed(t, scn, "LAMPGAP")
    assert len(gaps) == 2
    assert low <= gaps[0] < high, gaps          # the dark reading waited this long


# ---------------------------------------------------------------------------
# 4.3.53: the blue's side follows the direction of pass 1 (the tester Nelson's report of
# 20 Nov 2026 on a real i1Pro 2: after a right-to-left first pass the LEFT blue still blinked)
# ---------------------------------------------------------------------------
BLUE_RIGHT_SHA256 = "c8c07dfd2d166bab2a7d31efcfaf126da186f668c5973de763f0d4a2169a225d"


def _blue_data(t: str, scn: str) -> bytes:
    wire = _wire(t, scn)
    (i,) = _blue_writes(wire)
    assert wire[i - 1] == "CTL d6 000002be"
    return bytes.fromhex(wire[i].split()[3])


def _net(t: str, scn: str) -> "tuple[int, int]":
    ln = [x for x in t.splitlines() if x.startswith(f"{scn} NET ")]
    assert ln, scn
    a, b = ln[-1].split()[2:4]
    return int(a), int(b)


def test_after_a_left_to_right_pass_1_the_blue_is_todays_left_blue(traces):
    t = traces["i1pro2_dual_lights_test"]
    assert hashlib.sha256(_blue_data(t, "blue_side_ltr")).hexdigest() == BLUE_SHA256
    net, known = _net(t, "blue_side_ltr")
    assert known == 1 and net < -100            # the recorded sign of a left-to-right pass
    # and every request of that life is the 4.3.52 life's (the default is left to right)
    assert _wire(t, "blue_side_ltr") == _wire(t, "blue_sent")


def test_after_a_right_to_left_pass_1_the_blue_is_on_the_right_with_only_the_side_changed(traces):
    t = traces["i1pro2_dual_lights_test"]
    right = _blue_data(t, "blue_side_rtl")
    left = _blue_data(t, "blue_side_ltr")
    assert hashlib.sha256(right).hexdigest() == BLUE_RIGHT_SHA256 and len(right) == 702
    diff = [i for i in range(702) if right[i] != left[i]]
    assert len(diff) == 116 and all(left[i] == 0x20 and right[i] == 0x04 for i in diff)
    assert right[:12] == left[:12]               # the same header, length and repeat
    net, known = _net(t, "blue_side_rtl")
    assert known == 1 and net > 100
    # nothing else on the wire differs from the left-to-right life
    w_r, w_l = _wire(t, "blue_side_rtl"), _wire(t, "blue_side_ltr")
    assert len(w_r) == len(w_l)
    assert [a for a, b in zip(w_r, w_l) if a != b] == [w_r[_blue_writes(w_r)[0]]]


def test_when_pass_1s_direction_is_not_known_the_blue_stays_left(traces):
    t = traces["i1pro2_dual_lights_test"]
    assert hashlib.sha256(_blue_data(t, "blue_side_unknown")).hexdigest() == BLUE_SHA256
    assert _net(t, "blue_side_unknown")[1] == 0


@pytest.mark.parametrize("scn", ["blue_side_rtl_lights_off", "blue_side_rtl_single"])
def test_without_the_lights_or_the_dual_scan_no_blue_on_either_side(traces, scn):
    assert not _blue_writes(_wire(traces["i1pro2_dual_lights_test"], scn))


def test_the_right_blue_is_the_left_with_argylls_blue_right_mask_in_the_programs_file():
    src = (ROOT / "native" / "instlib" / "cq_i1pro2_programs.h").read_text(encoding="utf-8")
    assert "static const unsigned char cq_lights_seq_blue_right[702] = {" in src
    assert BLUE_RIGHT_SHA256 in src
    d = _driver()
    assert "#define CQ_LIGHTS_BLUE_RIGHT 8" in d and "#define CQ_BLUE_SIDE_STEPS 100" in d
    b = _body(d, "int i1pro2_cq_lights_second_pass(void *pp) {")
    assert "known && net > CQ_BLUE_SIDE_STEPS" in b and "which = CQ_LIGHTS_BLUE_RIGHT" in b


def test_the_helper_logs_the_blues_side_and_its_ruler_count():
    h = _helper()
    assert '"blue_right" };' in h
    assert '\\"side\\":\\"%s\\"' in h and "ruler_net" in h and "direction_known" in h


def test_the_right_blue_is_said_as_the_blue_and_its_side_goes_to_the_app_log(qapp, caplog):
    """4.3.53: the helper's "blue_right" (after a right-to-left first pass) reads in the
    Measure log as the blue does; the app log says the side and the ruler count."""
    with caplog.at_level("INFO"):
        out = _events(qapp, [{"event": "lights", "sent": "blue_right", "side": "right",
                              "ruler_net": 412, "direction_known": True}])
    assert out == ["[Engine] Instrument lights (beta): blue. The second pass of this strip is due."]
    msg = [r.getMessage() for r in caplog.records if "second_pass_due" in r.getMessage()]
    assert msg and "sent=blue_right" in msg[0] and "side=right" in msg[0] \
        and "ruler_net=412" in msg[0]
