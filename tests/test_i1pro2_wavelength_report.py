"""4.3.59: the i1Pro 2's wavelength offset is reported in the log, and nothing sent changes.

A tester's i1iO table strips showed a -1.25 nm shift. Every table row runs in a new helper
process that does not calibrate: it reads with what ArgyllCMS's i1pro_restore_calibration
restored when the instrument was opened, and the filters take the restored offset only when
mode 0's wavelength calibration was restored (i1pro_imp_init). A calibration file that fails
its identification, or a mode whose settings differ, left the EEPROM's factory filters, and
ArgyllCMS said so only in its debug log.

The helper now prints one "wavelength" event after opening an i1Pro 2 and after each
calibration: the offset the filters use, and whether it came from a calibration in that
process, the restored calibration file, or the factory filters. The table writes it as one
line in its session log and the app log; the hand reader writes it to the app log.

Pinned here:
* through the REAL driver on the fake USB layer (native/chartread_helper/tests/
  i1pro2_startcal_test.c, run "wl"): each of the three sources, and two ways a file is not
  used (a mode whose settings differ, a file that fails its identification);
* the report makes no USB call (counted on the fake layer), the driver lines it adds only
  assign ChromIQ's own variables, and the report function calls nothing that reaches the
  instrument;
* the line in the table session log and the app log for each source, and the hand reader's
  app log line;
* the helper's build string and the table reader's pin.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pytest

from tests.test_i1pro3_lights_modes import _build_and_run

ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "native" / "chartread_helper"
INSTLIB = ROOT / "native" / "instlib"


@pytest.fixture(scope="module")
def trace(tmp_path_factory) -> str:
    # ArgyllCMS saves its calibration after each one: into this scratch (XDG_CACHE_HOME)
    cache = tmp_path_factory.mktemp("wl_cache")
    return _build_and_run(tmp_path_factory, "i1pro2_startcal_test", args=(cache, "wl"))


def _events(text: str, scn: str) -> "list[dict]":
    out = []
    for ln in text.splitlines():
        if ln.startswith(scn + " WLEVENT "):
            body = ln.split(" WLEVENT ", 1)[1]
            assert body != "none", ln
            out.append(json.loads(body))
    assert out, f"no wavelength event in scenario {scn}"
    return out


def _io(text: str) -> "list[int]":
    return [int(ln.rsplit(" ", 1)[1]) for ln in text.splitlines() if " WLIO " in ln]


# ---------------------------------------------------------------------------
# The three sources, through the real driver
# ---------------------------------------------------------------------------

def test_no_file_reads_with_the_factory_filters(trace):
    (ev,) = _events(trace, "wl-nofile")
    assert ev["source"] == "factory" and ev["restore"] == "no_file"
    assert ev["offset_nm"] == 0.0 and ev["age_s"] == -1


def test_a_calibration_in_this_process_is_reported_with_its_offset(trace):
    opened, calibrated = _events(trace, "wl-fresh")
    assert opened["when"] == "open" and opened["source"] == "factory"
    assert calibrated["when"] == "calibrated" and calibrated["source"] == "calibration"
    # the harness's invented LED peak sits 0.3 raw bins off the reference; with its
    # polynomial (3.1 nm per bin, falling) that is -0.93 nm, as ArgyllCMS's own log says
    assert calibrated["offset_raw"] == pytest.approx(0.300, abs=1e-3)
    assert calibrated["offset_nm"] == pytest.approx(-0.930, abs=1e-3)


def test_the_next_process_reads_with_the_restored_file(trace):
    (ev,) = _events(trace, "wl-file")
    assert ev["source"] == "file" and ev["restore"] == "read"
    assert ev["offset_nm"] == pytest.approx(-0.930, abs=1e-3)
    assert ev["modes_restored"] == 9 and ev["modes_skipped"] == 0
    assert ev["age_s"] >= 0


def test_a_mode_whose_settings_differ_falls_back_to_the_factory_filters(trace):
    (ev,) = _events(trace, "wl-modes")
    assert ev["source"] == "factory" and ev["restore"] == "read"
    assert ev["modes_skipped"] == 1 and ev["modes_restored"] == 8
    assert ev["offset_nm"] == 0.0


def test_a_file_that_fails_its_identification_falls_back_to_the_factory_filters(trace):
    (ev,) = _events(trace, "wl-ident")
    assert ev["source"] == "factory" and ev["restore"] == "identification"
    assert ev["modes_restored"] == 0


# ---------------------------------------------------------------------------
# Reporting only: nothing sent changes
# ---------------------------------------------------------------------------

def test_the_report_makes_no_usb_call(trace):
    io = _io(trace)
    assert len(io) == 6 and set(io) == {0}


def _wl_pairs(key: str):
    from tests.test_engine_embeds_a_numeric_calibration import _vendor_module
    return _vendor_module()[key]


def _added(pairs) -> str:
    code = "\n".join(ln for old, new in pairs for ln in new.splitlines()
                     if ln not in set(old.splitlines()))
    return re.sub(r"/\*.*?\*/", "", code, flags=re.S)


NEVER = ("usb_", "icom", "EEProm", "eeprom", "trigger", "i1pro_update_log", "write_",
         "fopen", "send", "0xD", "0xC", "msec_sleep")


def test_the_driver_lines_only_set_chromiqs_own_variables():
    code = _added(_wl_pairs("I1PRO_IMP_C_WL_459"))
    for never in NEVER:
        assert never not in code, never
    statements = [s.strip() for s in re.split(r"[;{}]", code) if s.strip()]
    for st in statements:
        if st.startswith(("#include", "int ", "double ", "if (!hr && refl)")):
            continue
        assert re.match(r"^i1pro_cq_wl_\w+( = i1pro_cq_wl_\w+)? (=|\|=) ", st), st
    tree = (INSTLIB / "i1pro_imp.c").read_text(encoding="utf-8", errors="surrogateescape")
    for _old, new in _wl_pairs("I1PRO_IMP_C_WL_459"):
        assert tree.count(new) == 1


def test_the_report_function_reads_only():
    src = (INSTLIB / "cq_i1pro2_wlreport.h").read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    for never in NEVER:
        assert never not in code.replace("snprintf", ""), never
    # the calibration file's layout depends on these structs' sizes: none grew
    h = (INSTLIB / "i1pro_imp.h").read_text(encoding="utf-8", errors="surrogateescape")
    added_h = _added(_wl_pairs("I1PRO_IMP_H_WL_459"))
    assert "extern" in added_h and "struct" not in added_h
    assert all(new in h for _o, new in _wl_pairs("I1PRO_IMP_H_WL_459"))


def test_the_helper_emits_it_where_it_should_and_nowhere_else():
    cal = (HELPER / "chromiq_cal.c").read_text(encoding="utf-8")
    body = cal[cal.index("void cq_emit_wavelength(inst *it, const char *when) {"):]
    body = body[:body.index("\n}\n")]
    assert "instI1Pro2" in body and "i1pro2_cq_wl_report(" in body and "cq_emit_raw(" in body
    for never in ("calibrate(", "write", "send", "usb", "set_mode", "trigger"):
        assert never not in re.sub(r"/\*.*?\*/", "", body, flags=re.S), never
    # after each successful calibration (the session's and the one the user asks for)
    assert cal.count('cq_emit_wavelength(p, "calibrated");') == 2
    ts = (HELPER / "chromiq_tablescan.c").read_text(encoding="utf-8")
    i = ts.index('"{\\"event\\":\\"tscan_instrument\\"')
    assert ts.index('cq_emit_wavelength(it, "open");') > i
    assert ts.count("cq_emit_wavelength(") == 1
    cr = (HELPER / "chromiq_chartread.c").read_text(encoding="utf-8", errors="replace")
    i = cr.index('"{\\"event\\":\\"instrument\\",\\"model\\":\\"%s\\",\\"chart_model\\"')
    assert cr.index('cq_emit_wavelength(it, "open");') > i
    assert cr.count("cq_emit_wavelength(") == 1


def test_the_harness_opens_the_way_the_driver_does():
    """The harness's open_like_init stands for i1pro_imp_init's restore: the same two steps."""
    tree = (INSTLIB / "i1pro_imp.c").read_text(encoding="utf-8", errors="surrogateescape")
    i = tree.index("\t/* Restore the all modes calibration from the local system */\n"
                   "\ti1pro_restore_calibration(p);\n")
    block = tree[i:i + 900]
    assert "if (m->ms[0].wl_valid) {" in block
    assert block.index("i1pro_compute_wav_filters(p, 0, 0)") \
        < block.index("i1pro_compute_wav_filters(p, 0, 1)")


# ---------------------------------------------------------------------------
# The log lines
# ---------------------------------------------------------------------------

class _Log:
    def __init__(self):
        self.lines: "list[tuple[str, str]]" = []

    def __call__(self, kind, text):
        self.lines.append((kind, text))


@pytest.mark.parametrize("scn, idx, words", [
    ("wl-fresh", 1, "fitted by a wavelength calibration in this reader process"),
    ("wl-file", 0, "restored from the saved calibration file"),
    ("wl-ident", 0, "the instrument's factory filters"),
])
def test_one_line_in_the_table_log_and_the_app_log_for_each_source(trace, caplog, scn, idx,
                                                                     words):
    from workflow.i1io.table.reader import _Proc
    ev = _events(trace, scn)[idx]
    proc = object.__new__(_Proc)
    proc.log = _Log()
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        proc._wavelength(ev)
    (kind, text), = proc.log.lines
    assert kind == "DATA" and text.startswith("wavelength offset ") and words in text
    assert f"{ev['offset_nm']:+.3f} nm" in text
    app = [r.getMessage() for r in caplog.records
           if r.getMessage().startswith("i1pro2 wavelength:")]
    assert len(app) == 1 and "where=table" in app[0] and f"source={ev['source']}" in app[0]


def test_the_hand_reader_writes_it_to_the_app_log(trace, caplog, qapp):
    from workflow.measure_manager import MeasureManager

    class _Runner:
        is_running = True

        def write_stdin(self, _data):
            raise AssertionError("a wavelength event must send nothing")

    m = MeasureManager(_Runner())
    m._engine_active = True
    ev = _events(trace, "wl-file")[0]
    with caplog.at_level(logging.INFO):
        m._handle_engine_line(json.dumps(ev), lambda _s: None)
    msgs = [r.getMessage() for r in caplog.records]
    assert any(s.startswith("i1pro2 wavelength:") and "where=hand" in s for s in msgs)
    assert any("restored from the saved calibration file" in s for s in msgs)


# ---------------------------------------------------------------------------
# The build
# ---------------------------------------------------------------------------

def test_the_bundled_helper_is_this_build():
    from workflow.i1io.table.reader import HELPER_BUILD
    ext = (HELPER / "chromiq_ext.h").read_text(encoding="utf-8")
    assert '"chromiq-chartread 2026-11-23c ' in ext and "+wavelength-report\"" in ext
    assert HELPER_BUILD == "2026-11-23c"
    exe = ROOT / "native" / "chromiq-chartread"
    if not exe.is_file():
        pytest.skip("no bundled helper in this checkout")
    data = exe.read_bytes()
    assert b"chromiq-chartread 2026-11-23c " in data and b"+wavelength-report" in data
    assert b'{"event":"wavelength","when":"%s",%s}' in data
