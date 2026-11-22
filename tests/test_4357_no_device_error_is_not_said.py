"""A refused dual pass no longer says "(No device error)" (4.3.57, item 16).

ArgyllCMS's `interp_error` of a misread with no device code is "No device
error"; the reading helper reports every refused dual pass that way, so the
Measure log said "Strip read failed due to misread (No device error)" each
time, as if the device had failed. A real device error keeps its words.
"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent))
from test_knut_5956210745_next_strip_after_a_read import _session  # noqa: E402

from workflow.measure_manager import without_no_device_error  # noqa: E402


def test_the_phrase_goes_and_a_real_error_stays():
    assert without_no_device_error(
        "Strip read failed due to misread (No device error)") == \
        "Strip read failed due to misread"
    assert without_no_device_error("No device error") == ""
    real = "Strip read failed due to misread (Strip read too fast)"
    assert without_no_device_error(real) == real


def test_the_measure_log_and_the_window_leave_it_out(qapp):
    """MUTATION: pass `line` instead of `without_no_device_error(line)` to
    `on_line` in `_handle_engine_line` and the log line keeps it."""
    m, _r = _session()
    lines, errors = [], []
    m.strip_error.connect(errors.append)
    m._handle_engine_line(
        "Strip read failed due to misread (No device error)", lines.append)
    m._handle_engine_line(json.dumps(
        {"event": "error", "kind": "misread", "detail": "No device error"}),
        lines.append)
    assert lines == ["Strip read failed due to misread"]
    assert errors == ["misread"]
    m._handle_engine_line(json.dumps(
        {"event": "error", "kind": "misread",
         "detail": "Strip read too fast"}), lines.append)
    assert errors[-1] == "Strip read too fast"
