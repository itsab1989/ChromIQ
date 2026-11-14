"""Which USB step failed, and the i1Pro 2's paused Beta parts (4.3.36).

A tester's real i1Pro 2 ended strips with "The instrument lost communication
with the computer", and nothing said which transfer had failed (the helper
sent ``"detail":""``; ArgyllCMS's driver folds every USB error into one code).
Since 4.3.36 the helper WATCHES the instrument's USB entry points
(native/chartread_helper/chromiq_usbwatch.c) and puts the first failed
transfer of the reading into the error event. And until a tester confirms a
fix, an i1Pro 2 is given neither lights choice and no ruler check
(native/chartread_helper/cq_beta_pause.h).

Both are proved here on the FAKE USB layer, through the REAL vendored driver:

* the watch is read-only: every existing fake-USB life (the i1Pro 2 and
  i1Pro 3 lights in every combination, the ruler scans, the original i1Pro)
  prints the same wire with the watch installed as without it, and the
  fixtures of 4.3.33 / 4.3.34 / the ruler base still match the watched run;
* each failing step, injected on the fake layer, is named in the event's
  fields (the measure trigger, the measurement read, the button read, a light
  write; which trigger of the strip; the ICOM code; bytes; times);
* an i1Pro 2 gets 4.3.33's bytes for every stored lights combination, and an
  i1Pro 3 exactly what it got in 4.3.35.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HELPER_SRC = ROOT / "native" / "chartread_helper"
DATA = ROOT / "tests" / "data"
FIX_4333 = DATA / "i1pro2_lights_v4333_trace.txt"
FIX2_4334 = DATA / "i1pro2_lights_v4334_trace.txt"
FIX3_4334 = DATA / "i1pro3_lights_v4334_trace.txt"
FIX_RULER = DATA / "i1pro_ruler_base_trace.txt"

TARGETS = ("usb_failure_detail_test",
           "i1pro2_lights_modes_test", "i1pro2_lights_modes_test_watched",
           "i1pro3_lights_modes_test", "i1pro3_lights_modes_test_watched",
           "i1pro_ruler_scan_test", "i1pro_ruler_scan_test_watched")


@pytest.fixture(scope="module")
def runs(tmp_path_factory) -> "dict[str, str]":
    """Every target above, built once in one folder and run once."""
    if sys.platform == "win32":
        pytest.skip("the fake-USB driver tests are built on macOS and Linux only")
    cmake = shutil.which("cmake")
    if cmake is None:
        pytest.skip("cmake not available: the helper is not built here")
    build = tmp_path_factory.mktemp("usbwatch") / "build"
    subprocess.run([cmake, "-S", str(HELPER_SRC), "-B", str(build),
                    "-DCMAKE_BUILD_TYPE=Release"],
                   check=True, capture_output=True, timeout=600)
    jobs = str(max(2, (os.cpu_count() or 4) // 2))
    r = subprocess.run([cmake, "--build", str(build), "--target", *TARGETS,
                        "-j", jobs], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1200)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    out = {}
    for t in TARGETS:
        exe = next(p for p in build.rglob(t + "*")
                   if p.is_file() and os.access(p, os.X_OK)
                   and p.name in (t, t + ".exe"))
        rr = subprocess.run([str(exe)], capture_output=True, text=True,
                            encoding="utf-8", timeout=300)
        assert rr.returncode == 0 and rr.stdout.rstrip().endswith("ALL DONE"), \
            t + "\n" + rr.stdout[-2000:] + rr.stderr[-2000:]
        out[t] = rr.stdout
    return out


def _fixture(path: Path) -> str:
    return "\n".join(ln for ln in path.read_text(encoding="utf-8").splitlines()
                     if not ln.startswith("#"))


def _lines(text: str, scn: str) -> "list[str]":
    return [ln.split(" ", 1)[1] for ln in text.splitlines()
            if ln.startswith(scn + " ")]


def _scenarios(text: str) -> "list[str]":
    seen = []
    for ln in text.splitlines():
        s = ln.split(" ", 1)[0]
        if s and s != "ALL" and s not in seen:
            seen.append(s)
    return seen


_WIRE = re.compile(r"^(CTL|WR|RD|CANCEL)\b")


def _wire(lines):
    return [ln for ln in lines if _WIRE.match(ln)]


def _no_timing(lines):
    return [ln for ln in lines if not ln.startswith("MEASURE-MS")]


# ---------------------------------------------------------------------------
# The watch changes nothing on the wire
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("target", ["i1pro2_lights_modes_test",
                                    "i1pro3_lights_modes_test",
                                    "i1pro_ruler_scan_test"])
def test_every_existing_life_is_the_same_with_the_watch(runs, target):
    plain, watched = runs[target], runs[target + "_watched"]
    scns = _scenarios(plain)
    assert len(scns) >= 10 and scns == _scenarios(watched)
    for scn in scns:
        a, b = _no_timing(_lines(plain, scn)), _no_timing(_lines(watched, scn))
        assert _wire(a) == _wire(b), scn
        assert a == b, scn


@pytest.mark.parametrize("fixture,target", [
    (FIX_4333, "i1pro2_lights_modes_test_watched"),
    (FIX2_4334, "i1pro2_lights_modes_test_watched"),
    (FIX3_4334, "i1pro3_lights_modes_test_watched"),
])
def test_the_watched_lights_lives_match_the_release_fixtures(runs, fixture,
                                                             target):
    fx = _fixture(fixture)
    checked = 0
    for scn in _scenarios(fx):
        if fixture is FIX3_4334:
            want = [ln for ln in _no_timing(_lines(fx, scn))
                    if ln.split(" ", 1)[0] not in ("CHOICES", "SENT")]
            got = [ln for ln in _no_timing(_lines(runs[target], scn))
                   if ln.split(" ", 1)[0] not in ("CHOICES", "SENT")]
        else:
            want, got = _lines(fx, scn), _lines(runs[target], scn)
        assert got == want, scn
        checked += 1
    assert checked >= 3


@pytest.mark.parametrize("scn", ["off_i1pro2", "off_i1pro"])
def test_the_watched_ruler_scans_match_the_base_fixture(runs, scn):
    base = FIX_RULER.read_text(encoding="utf-8")
    got = [ln for ln in runs["i1pro_ruler_scan_test_watched"].splitlines()
           if ln.startswith(scn + " ")]
    assert got and got == [ln for ln in base.splitlines()
                           if ln.startswith(scn + " ")]


# ---------------------------------------------------------------------------
# The i1Pro 2's paused choices, and the i1Pro 3's unchanged ones
# ---------------------------------------------------------------------------
COMBOS = ["ready_off", "signals_off", "ready_lefton", "signals_lefton"]


@pytest.mark.parametrize("combo", COMBOS)
def test_an_i1pro2_gets_4_3_33s_bytes_whatever_is_stored(runs, combo):
    """Through the helper's own mapping (cq_lights_choices_for): with the
    lights option on and any stored combination, an i1Pro 2's whole life is
    byte for byte 4.3.33's (the fixture's "on_ready_off")."""
    want = _lines(_fixture(FIX_4333), "on_ready_off")
    assert want
    got = _lines(runs["i1pro2_lights_modes_test"], f"v4336_{combo}")
    assert got == want


@pytest.mark.parametrize("combo", COMBOS)
def test_an_i1pro3_gets_what_4_3_35_gave_it(runs, combo):
    """The i1Pro 3 is given the stored combination unchanged: each life is
    the one this tree's driver makes for that combination (which the other
    i1Pro 3 tests pin, "on_ready_off" against 4.3.34's fixture)."""
    t = runs["i1pro3_lights_modes_test"]

    def comparable(scn):
        # SENT is the test's own print of the helper's callback, which the
        # C test installs only after its "on_ready_off" life: not the wire
        return [ln for ln in _no_timing(_lines(t, scn))
                if not ln.startswith("SENT ")]
    assert comparable(f"v4336_{combo}") == comparable(f"on_{combo}")
    assert _wire(_lines(t, f"v4336_{combo}")) == _wire(_lines(t, f"on_{combo}"))


def test_only_these_wire_sequences_reach_an_i1pro2():
    """What 4.3.36 leaves an i1Pro 2: steady white, the 2-second off over the
    white, the immediate off at the close (and no result programs)."""
    from tests.test_i1pro2_lights_modes import _programs
    names = _programs()
    sent = []
    for ln in _lines(_fixture(FIX_4333), "on_ready_off"):
        p = ln.split(" ")
        if p[0] == "WR" and p[1] == "03":
            sent.append(names.get(p[2], "UNKNOWN"))
    assert set(sent) == {"WHITE", "OFF_SLOW", "OFF_NOW"}


def test_the_pause_lives_in_the_helper_in_one_place():
    src = (HELPER_SRC / "chromiq_chartread.c").read_text(
        encoding="utf-8", errors="surrogateescape")
    sess = src[src.index("static void cq_lights_for_session("):]
    sess = sess[:sess.index("\n}\n")]
    assert "cq_lights_choices_for(cq_lights_gen, cq_lights_signals," in sess
    assert "i1pro2_cq_lights_options(it, sig, left);" in sess
    assert "i1pro3_cq_lights_options(it, sig, left);" in sess
    assert "_cq_lights_options(it, cq_lights_signals" not in sess
    hdr = (HELPER_SRC / "cq_beta_pause.h").read_text(encoding="utf-8")
    assert "if (gen == 2) {" in hdr and "return gen == 2;" in hdr
    # the ruler: for an i1Pro 2 nothing of the driver is called
    rul = src[src.index("static void cq_ruler_for_session("):]
    rul = rul[:rul.index("\n}\n")]
    paused = rul[rul.index("it->dtype == instI1Pro2 && cq_ruler_paused_for(2)"):]
    paused = paused[:paused.index("} else if")]
    assert 'why = "paused";' in paused
    assert "i1pro2_cq_ruler" not in paused


# ---------------------------------------------------------------------------
# Each failing step, named
# ---------------------------------------------------------------------------
def _event(runs, scn) -> dict:
    line = next(ln for ln in runs["usb_failure_detail_test"].splitlines()
                if ln.startswith(scn + " JSON "))
    fields = line.split(" JSON ", 1)[1]
    return json.loads('{"event":"error","kind":"coms","detail":""'
                      + fields + "}")


def test_a_failed_trigger_is_named_before_the_read_it_spoiled(runs):
    ev = _event(runs, "trigger_fails")
    assert ev["usb_step"] == "measure_trigger" and ev["usb_failures"] == 2
    first, then = ev["usb"]
    assert (first["kind"], first["code"], first["icom"]) == \
        ("control", "0xD4", "0x000200")
    assert first["trigger"] == 1 and first["asked"] == 14
    assert first["tout_ms"] == 2000
    assert (then["step"], then["code"], then["icom"]) == \
        ("measurement_read", "0x82", "0x004000")


def test_a_failed_measurement_read(runs):
    ev = _event(runs, "read_fails")
    assert ev["usb_step"] == "measurement_read"
    (f,) = ev["usb"]
    assert f["icom"] == "0x004000" and f["bytes"] == 0 and f["trigger"] == 1
    assert f["asked"] > 0 and f["tout_ms"] > 0 and f["took_ms"] >= 0


def test_the_trigger_number_says_which_reading_of_the_strip(runs):
    """An i1Pro reads a strip with two triggers: the dark reading at the
    start (a calibration step), then the scan."""
    ev = _event(runs, "second_read_fails")
    assert ev["usb"][0]["trigger"] == 2 and ev["usb"][0]["icom"] == "0x000100"


def test_the_original_i1pros_trigger(runs):
    ev = _event(runs, "i1pro_trigger_fails")
    assert ev["usb_step"] == "measure_trigger"
    assert ev["usb"][0]["code"] == "0xC0"


def test_the_button_read(runs):
    assert _event(runs, "button_fails")["usb_step"] == "button_read"
    # a timeout is how the button thread's wait ends: not a failure
    ev = _event(runs, "button_timeout_is_routine")
    assert ev["usb_step"] == "none" and ev["usb"] == []


def test_a_light_write(runs):
    ev = _event(runs, "light_fails")
    assert ev["usb_step"] == "light"
    assert ev["usb"][0]["code"] == "0x03" and ev["usb"][0]["asked"] == 32


def test_nothing_failed_and_a_short_read_is_not_a_failure(runs):
    ev = _event(runs, "nothing_fails")
    assert ev["usb_step"] == "none" and ev["usb_failures"] == 0


def test_the_last_light_program_and_its_distance_to_the_trigger(runs):
    ev = _event(runs, "light_timing")
    assert ev["light"] == "off_slow"
    assert 25 <= ev["light_to_trigger_ms"] < 2000


def test_a_new_reading_forgets_the_last_ones_failures(runs):
    assert _event(runs, "begin_forgets")["usb_step"] == "none"


@pytest.mark.parametrize("scn,step", [
    ("i1pro3_trigger", "measure_trigger"),
    ("i1pro3_trigger_emis", "measure_trigger"),
    ("i1pro3_read", "measurement_read"),
    ("i1pro3_ruler", "ruler_read"),
    ("i1pro3_button", "button_read"),
    ("i1pro3_button_timeout", "none"),
    ("i1pro3_light_ctl", "light"),
    ("i1pro3_light", "light"),
    ("i1pro3_other", "control"),
])
def test_the_i1pro3s_transfers_by_name(runs, scn, step):
    assert _event(runs, scn)["usb_step"] == step


def test_a_forgotten_watch_says_nothing_and_gives_the_originals_back(runs):
    text = runs["usb_failure_detail_test"]
    assert "forgotten JSON \n" in text or "forgotten JSON" in text.splitlines()
    assert "forgotten RESTORED 1" in text


def test_the_helper_sends_the_fields_on_both_communication_errors():
    src = (HELPER_SRC / "chromiq_chartread.c").read_text(
        encoding="utf-8", errors="surrogateescape")
    assert 'cq_emit_error("coms", "")' not in src
    assert src.count("cq_emit_coms_error(it, rv);") == 2
    assert src.count("cq_usbwatch_begin();") == 2
    body = src[src.index("static void cq_emit_coms_error("):]
    body = body[:body.index("\n}\n")]
    # the two fields the app has always read stay as they were
    assert '\\"kind\\":\\"coms\\",\\"detail\\":\\"\\"' in body


def test_the_watch_only_looks():
    """Each wrapper returns exactly what the original returned, called with
    exactly its own arguments; nothing else touches the instrument."""
    src = (HELPER_SRC / "chromiq_usbwatch.c").read_text(encoding="utf-8")
    assert "int se = cq_uw_ctl(p, requesttype, request, value, index, rwbuf, " \
           "rwsize,\n\t                   xferred, tout);" in src
    assert "int se = cq_uw_rd(p, cancelt, ep, buf, bsize, done, tout);" in src
    assert "int se = cq_uw_wr(p, cancelt, ep, buf, bsize, done, tout);" in src
    assert src.count("return se;") == 3
    for forbidden in ("usb_cancel_io", "usb_resetep", "usb_clearhalt",
                      "usb_wait_io"):
        assert forbidden not in src


def test_the_lights_failure_names_every_program():
    """The diagnosis of 2026-11-14: a failed green2 was logged as "off"."""
    src = (HELPER_SRC / "chromiq_chartread.c").read_text(
        encoding="utf-8", errors="surrogateescape")
    f2 = src[src.index("static void cq_lights_failed(int seq"):]
    f2 = f2[:f2.index("\n}\n")]
    assert "cq_lights_name2(seq)" in f2 and '"off"' not in f2
    names = src[src.index("static const char *cq_lights_name2(int seq)"):]
    names = names[:names.index("\n}\n")]
    assert ('"white", "off_slow", "off_now",\n\t                               '
            '"pulse", "green2", "red2"') in names
    f3 = src[src.index("static void cq_lights_failed3(int seq"):]
    f3 = f3[:f3.index("\n}\n")]
    assert '{ "?", "ready", "green2", "red2", "off" }' in f3
