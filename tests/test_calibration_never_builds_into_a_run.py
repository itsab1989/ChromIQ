"""Run type = Calibration never builds into a profiling run (#182).

Knut, #182 5964478612 (2026-10-03), and his log at 02:27:01: a Generate whose
patch set was ``test.ti1``, then ``archived test.ti3 -> old/2026-10-03_022701/``
and ``archived test.icc``. The bar said Calibration; the build was run4's own
patch set, re-laid out into run4. ``_on_generate`` asked "Calibration?" only
after its preset and patch-set branches had already returned, and every one of
those builds into the run the bar's Profile run names. cal/ was empty, so the
§4 window had nothing to ask about and none appeared.

calibration_run_type §4.2: Run type = Calibration sets ``cal_target``; §4.4:
cal/ and a run protect each other. These tests drive the real tab: every way a
build can start (Generate with each kind of binding, a built-in preset, Load
patch set, the live preview, a direct .ti1 build) leaves run1's files byte for
byte as they were, and Generate builds targen's calibration chart instead.
"""
from __future__ import annotations

import pytest

from core.measurement_target import RUN_TYPE_CALIBRATION
from tests._cal_target_fixture import (Refusals, fingerprint, make_window,
                                       show_run, write_run_chart)


@pytest.fixture
def win(qapp, tmp_path):
    w = make_window(qapp, tmp_path)
    run1 = w._file_mgr.project().current_run()
    files = write_run_chart(run1, given=True)
    show_run(w, qapp, run1.id)
    yield w, run1, files
    w.close()


@pytest.fixture
def calls(win, monkeypatch):
    """Record every build the creator is asked for, and build nothing."""
    w, _run1, _files = win
    tc = w._tab_chart
    got = {"targen": [], "from_ti1": []}
    monkeypatch.setattr(tc._creator, "generate",
                        lambda params, *a, **k: got["targen"].append(params))
    monkeypatch.setattr(
        tc._creator, "load_ti1_and_generate_preview",
        lambda ti1, params, *a, **k: got["from_ti1"].append(ti1))
    refusals = Refusals()
    monkeypatch.setattr("ui.tabs.tab_chart.InfoDialog", refusals)
    got["refusals"] = refusals.shown
    return got


def _to_calibration(w, qapp):
    w._target_ctl.set_run_type(RUN_TYPE_CALIBRATION)
    qapp.processEvents()
    assert w._tab_chart._calibration_selected()


def _generate(tc, monkeypatch):
    monkeypatch.setattr(type(tc), "_confirm_displacing_results",
                        lambda self, *a, **k: True)
    monkeypatch.setattr(type(tc), "_handle_target_rename",
                        lambda self, *a, **k: True)
    tc._on_generate()


def test_showing_the_run_binds_its_own_patch_set(win):
    """The precondition the fault needs: run1's chart came from a patch set
    of its own, so showing it binds that set (#147)."""
    w, _run1, files = win
    assert w._tab_chart._preset_ti1_path == files["ti1"]


@pytest.mark.parametrize("binding", ["patch_set", "tc918", "knut",
                                     "prebuilt", "applied"])
def test_generate_in_calibration_builds_targen_into_cal(
        win, calls, qapp, monkeypatch, binding):
    """Whatever is still bound, Generate in Calibration is targen's ramp into
    cal/: no preset branch runs, run1 keeps every byte."""
    w, run1, files = win
    tc = w._tab_chart
    _to_calibration(w, qapp)
    before = fingerprint(run1.dir)
    # Whatever the scope rules drop on the way in, put the binding back:
    # these guards are the second line, and must hold on their own.
    sidelines = []
    for name in ("_generate_from_ti1", "_create_prebuilt_target",
                 "_import_applied_chart"):
        monkeypatch.setattr(type(tc), name,
                            lambda self, *a, _n=name, **k: sidelines.append(_n))
    if binding == "patch_set":
        tc._preset_ti1_path = files["ti1"]
        tc._preset_ti1_targen_sig = tc._targen_signature()
    elif binding == "tc918":
        tc._tc918_active = True
        tc._tc918_targen_sig = tc._targen_signature()
    elif binding == "knut":
        tc._knut_active = True
        tc._knut_targen_sig = tc._targen_signature()
    elif binding == "prebuilt":
        tc._prebuilt_active = True
        tc._prebuilt_key = "__any__"
        tc._prebuilt_targen_sig = tc._targen_signature()
        tc._prebuilt_printtarg_sig = tc._printtarg_signature()
    else:
        tc._applied_active = True
        tc._applied_src_dir = files["ti1"].parent
        tc._applied_stem = files["ti1"].stem
        tc._applied_targen_sig = tc._targen_signature()
        tc._applied_printtarg_sig = tc._printtarg_signature()

    _generate(tc, monkeypatch)

    assert sidelines == [], f"a preset branch ran in Calibration: {sidelines}"
    assert calls["from_ti1"] == []
    assert len(calls["targen"]) == 1, "targen was not asked for the chart"
    assert calls["targen"][0].cal_target is True, "the build was not for cal/"
    assert fingerprint(run1.dir) == before, "run1's files changed"


def test_a_builtin_preset_picked_in_calibration_builds_nothing(
        win, calls, qapp):
    """A built-in is a profiling chart built the moment it is picked. In
    Calibration it is refused, the dropdown goes back, nothing moves."""
    from ui.tabs.tab_chart import (BUILTIN_PRESET_KEYS,
                                   DISABLED_BUILTIN_PRESET_KEYS)

    w, run1, _files = win
    tc = w._tab_chart
    _to_calibration(w, qapp)
    before = fingerprint(run1.dir)
    was = tc._preset_combo.currentIndex()
    combo = tc._preset_combo
    ix = next((i for i in range(combo.count())
               if combo.itemData(i) in BUILTIN_PRESET_KEYS
               and combo.itemData(i) not in DISABLED_BUILTIN_PRESET_KEYS), -1)
    assert ix >= 0, "no built-in preset in the dropdown"
    tc._preset_combo.blockSignals(True)
    tc._preset_combo.setCurrentIndex(ix)
    tc._preset_combo.blockSignals(False)
    tc._on_preset_selected(ix)
    qapp.processEvents()

    assert calls["from_ti1"] == [] and calls["targen"] == []
    assert [t for t, _b in calls["refusals"]] == [
        "Not available for a calibration chart"]
    assert tc._preset_combo.currentIndex() == was
    assert not (tc._tc918_active or tc._knut_active or tc._prebuilt_active)
    assert fingerprint(run1.dir) == before


def test_load_patch_set_in_calibration_asks_for_no_file(
        win, calls, qapp, monkeypatch):
    w, run1, _files = win
    tc = w._tab_chart
    _to_calibration(w, qapp)
    before = fingerprint(run1.dir)
    asked = []
    monkeypatch.setattr("ui.tabs.tab_chart.open_file_dialog",
                        lambda *a, **k: asked.append(a) or "")
    tc._on_load_ti1()
    assert asked == [], "the file dialog opened in Calibration"
    assert calls["from_ti1"] == []
    assert len(calls["refusals"]) == 1
    assert tc._preset_ti1_path is None
    assert fingerprint(run1.dir) == before


def test_the_live_preview_does_not_render_in_calibration(
        win, calls, qapp, monkeypatch):
    """With the calibration chart (or anything) on screen, a turn of a layout
    knob used to lay those patches out into the profiling run (A4)."""
    w, run1, files = win
    tc = w._tab_chart
    _to_calibration(w, qapp)
    before = fingerprint(run1.dir)
    tc._settings.set("auto_update_preview", True)
    tc._current_ti1_path = files["ti1"]
    tc._last_auto_sig = None
    tc._auto_regenerate_preview()
    # …and the route itself refuses quietly, without a window.
    assert tc._generate_from_ti1(files["ti1"], ask=False,
                                 preview=True) is False
    assert calls["from_ti1"] == [] and calls["refusals"] == []
    assert fingerprint(run1.dir) == before


def test_a_direct_ti1_build_in_calibration_is_refused(win, calls, qapp):
    w, run1, files = win
    tc = w._tab_chart
    _to_calibration(w, qapp)
    before = fingerprint(run1.dir)
    assert tc._generate_from_ti1(files["ti1"]) is False
    assert calls["from_ti1"] == []
    assert len(calls["refusals"]) == 1
    assert tc._generate_btn.isEnabled(), "a refusal left the button greyed"
    assert fingerprint(run1.dir) == before


def test_the_log_label_says_who_asked():
    """Knut's log called a Generate on a bound patch set "live preview",
    because the label was keyed on `ask`, which the preset routes pass too."""
    import inspect

    from ui.tabs.tab_chart import TabChart

    src = inspect.getsource(TabChart._generate_from_ti1)
    assert '"live preview" if preview else "user"' in src
    assert '"live preview" if not ask' not in src


def test_the_refusal_names_no_em_dash():
    """New user-facing text (CLAUDE.md)."""
    import inspect

    from ui.tabs.tab_chart import TabChart

    src = inspect.getsource(TabChart._refuse_in_calibration)
    assert "—" not in src
