"""Independent review of the i1Pro 2 dual scan UI step (2026-11-18, 8dd817972).

Two faults found by reading the tab against the helper's C code
(native/chartread_helper/chromiq_dualdev.c cq_dd_strip). Each test is
``xfail(strict=True)``: it documents the fault and turns red (XPASS) the
day the fault is fixed, so the marker must then be removed.
"""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.dual_scan import session as D          # noqa: E402
from workflow.dual_scan import storage                # noqa: E402

CAPS = frozenset({storage.CAPABILITY, storage.DEVICE_CAPABILITY,
                  "i1pro3_conditions"})


class _S(dict):
    def get(self, k, d=None):
        return super().get(k, d)

    def set(self, k, v):
        self[k] = v


def _fake(tmp_path, strips=("A", "B")):
    from ui.tabs.tab_measure import TabMeasure
    run_dir = tmp_path / "P" / "runs" / "run1"
    run_dir.mkdir(parents=True, exist_ok=True)
    logged = []
    settings = _S({"i1pro3_conditions_beta": True, D.SETTING: True})
    fake = SimpleNamespace(
        _settings=settings, _ti1_path=run_dir / "P.ti1",
        _log=SimpleNamespace(appendPlainText=logged.append,
                             ensureCursorVisible=lambda: None),
        _manager=SimpleNamespace(_session_strips=[{"strip": s} for s in strips]),
        _preview=SimpleNamespace(set_notice=lambda *a, **k: None),
        _strip_name=lambda s: s,
        _hide_status_flash=lambda: None)
    fake._dual_strip_labels = lambda: TabMeasure._dual_strip_labels(fake)
    fake._dual_status = lambda t, d="": None
    fake._dual_prompt = lambda t, b: None
    return fake, logged


@pytest.mark.xfail(strict=True, reason=(
    "REVIEW 2026-11-18: a UV pass left by a command (goto / f / b while pass 2 "
    "was due) gives dual_pass_result uv_pass_missing with NO misread window "
    "(cq_dd_strip: *rv = rv2, the loop handles the key); _dual_failed stays "
    "set and the NEXT misread window, of another strip, says the second pass "
    "of strip A failed (also after M1 / M2 ended: dual_needs_ruler does not "
    "clear it). Fix: clear _dual_failed at every strip_ready "
    "(_on_stripe_changed) and on every dual_pass_result."))
def test_a_left_second_pass_never_names_itself_in_another_strips_window(
        qapp, tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    fake, _ = _fake(tmp_path)
    TabMeasure._dual_reset(fake)
    TabMeasure._on_dual_session(fake, {"active": True, "dual": True,
                                       "scale": 1.156, "chosen": "M1"})
    # strip A: pass 2 left by a command; no window follows
    TabMeasure._on_dual_pass_result(fake, {"what": "strip", "strip": "A",
                                           "ok": False,
                                           "why": "uv_pass_missing"})
    # the next strip B: no UV pass can be lined up any more (the ruler
    # stream was left), so M1 / M2 end and B is kept as M0
    fake._spot_session = False
    TabMeasure._dual_pass_one(fake, "B")
    TabMeasure._on_dual_pass_result(fake, {"what": "strip", "strip": "B",
                                           "ok": False,
                                           "why": "dual_needs_ruler"})
    TabMeasure._on_dual_ended(fake, "dual_dual_needs_ruler")
    # strip C, a single scan now, is an ordinary misread: its window must
    # not speak of strip A's second pass
    TabMeasure._dual_pass_one(fake, "C")
    assert "strip A" not in TabMeasure._dual_failure_html(fake)


@pytest.mark.xfail(strict=True, reason=(
    "REVIEW 2026-11-18: the pass record is named by the measurement's STEM "
    "(Run.dual_pass_record), not by its readings, and nothing clears it, so a "
    "NEW measurement into the same file (Replace) inherits the old one's "
    "strip states and its preset_done: Build Profile is then never pre-set "
    "for it, and a strip the new measurement has not read counts as having "
    "both passes. Fix: start a fresh PassRecord when the session is not a "
    "Continue Measurement (p.resume False), or key the record by the "
    "readings' hash as the conditions files are."))
def test_a_new_measurement_into_the_same_file_starts_a_fresh_pass_record(
        qapp, tmp_path):
    from core.file_manager import Run
    from ui.tabs.tab_measure import TabMeasure
    from workflow.dual_scan.record import PassRecord
    fake, _ = _fake(tmp_path)
    main = fake._ti1_path.with_suffix(".ti3")
    main.write_text("CTI3\n", encoding="latin-1")
    old = PassRecord(["A", "B"], chosen="M2", preset_done=True)
    old.helper_strip("A", True, "", "c0")
    old.helper_strip("B", True, "", "c0")
    old.save(Run.dual_pass_record(main))
    # a new measurement (not continued): only strip A read so far
    TabMeasure._dual_reset(fake)
    TabMeasure._on_dual_session(fake, {"active": True, "dual": True,
                                       "scale": 1.156, "chosen": "M1"})
    TabMeasure._on_dual_pass_result(fake, {"what": "strip", "strip": "A",
                                           "ok": True, "why": "",
                                           "pairing": "checked"})
    TabMeasure._dual_flush(fake, str(main), 1)
    rec = PassRecord.load(Run.dual_pass_record(main))
    assert not rec.preset_done
    assert ("B", "uv") in rec.missing()
