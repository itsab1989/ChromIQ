"""A binding survives its own build, and typing a name does not drop it.

The regression guard against the fix the #182 challenge rejected (2026-10-03):
"drop every binding in `_on_target_changed`". That handler is not "the target
changed". It runs on every keystroke in the project-name box, and on the
build's own landing on its New run (`_align_current_run_to_target`), which
happens in the middle of the build. Dropping there leaves a chart built from a
loaded patch set UNBOUND in its own run, and the next Generate after a layout
tweak makes different patches: #147, *"cost him thirteen printed pages"*, and
B8-1363.
"""
from __future__ import annotations

import pytest

from tests._cal_target_fixture import (bound, make_window, override_row_shown,
                                       show_run, write_run_chart)


@pytest.fixture
def win(qapp, tmp_path):
    w = make_window(qapp, tmp_path)
    proj = w._file_mgr.project()
    run1 = proj.current_run()
    write_run_chart(run1, given=False)
    show_run(w, qapp, run1.id)
    yield w, proj, run1
    w.close()


@pytest.fixture
def loaded(tmp_path):
    """A patch set of the user's own, outside any project."""
    p = tmp_path / "mine" / "my-patches.ti1"
    p.parent.mkdir(parents=True)
    rows = "\n".join(f"{i} {v} {v} {v} {v} {v} {v}"
                     for i, v in enumerate((100.0, 50.0, 0.0), 1))
    p.write_text('CTI1\n\nORIGINATOR "ChromIQ i1Profiler import"\n'
                 'COLOR_REP "iRGB"\n\nNUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n'
                 'SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n'
                 f'END_DATA_FORMAT\n\nNUMBER_OF_SETS 3\nBEGIN_DATA\n{rows}\n'
                 'END_DATA\n', encoding="utf-8")
    return p


def _load(w, qapp, monkeypatch, ti1, dest, builds):
    tc = w._tab_chart
    monkeypatch.setattr("ui.tabs.tab_chart.open_file_dialog",
                        lambda *a, **k: str(ti1))
    monkeypatch.setattr(type(tc), "_ti1_load_destination",
                        lambda self, src: dest)
    monkeypatch.setattr(type(tc), "_confirm_displacing_results",
                        lambda self, *a, **k: True)
    monkeypatch.setattr(
        tc._creator, "load_ti1_and_generate_preview",
        lambda path, params, *a, **k: builds.append((path, params)))
    tc._on_load_ti1()
    qapp.processEvents()
    # The build has come back: what `_on_generate_finished` leaves behind.
    tc._generate_btn.setEnabled(True)
    tc._layout_owned_by_build = False


def _layout_only_generate(w, monkeypatch, builds):
    tc = w._tab_chart
    monkeypatch.setattr(type(tc), "_handle_target_rename",
                        lambda self, *a, **k: True)
    tc._on_generate()
    return builds[-1][0]


def test_load_patch_set_into_a_new_run_stays_bound(win, loaded, qapp,
                                                   monkeypatch):
    w, proj, run1 = win
    tc = w._tab_chart
    builds = []
    _load(w, qapp, monkeypatch, loaded, "into_new", builds)
    assert len(builds) == 1 and builds[0][0] == loaded
    assert w._target_ctl.target.profile_run != run1.id, "no new run was made"
    # A refresh that changes nothing (Restore Used Chart, a cancelled load).
    w._target_ctl.changed.emit()
    qapp.processEvents()
    assert tc._preset_ti1_path == loaded, (
        "the build's own landing on its New run dropped the patch set")
    assert override_row_shown(tc)
    # A layout-only Generate lays the SAME patches out again.
    assert _layout_only_generate(w, monkeypatch, builds) == loaded


def test_load_patch_set_into_a_fresh_project_stays_bound(win, loaded, qapp,
                                                         monkeypatch):
    w, _proj, _run1 = win
    tc = w._tab_chart
    monkeypatch.setattr("ui.ti2_loader._ask_project_name",
                        lambda *a, **k: ("Fresh-From-Patches", False))
    builds = []
    _load(w, qapp, monkeypatch, loaded, "new", builds)
    assert len(builds) == 1
    assert w._file_mgr.get_target_name() == "Fresh-From-Patches"
    w._target_ctl.changed.emit()
    qapp.processEvents()
    assert tc._preset_ti1_path == loaded, (
        "landing on the fresh project dropped the patch set")
    assert _layout_only_generate(w, monkeypatch, builds) == loaded


def test_typing_a_name_does_not_drop_a_binding(win, loaded, qapp):
    w, _proj, run1 = win
    tc = w._tab_chart
    tc._rebind_patch_set_from_run(loaded, given=True)
    assert tc._preset_ti1_path == loaded
    for text in ("S", "So", "Some other name"):
        tc._manual_target_name_edit.setText(text)
        qapp.processEvents()
    assert tc._preset_ti1_path == loaded, "a keystroke dropped the binding"
    assert bound(tc) and override_row_shown(tc)
    assert w._target_ctl.target.profile_run == run1.id
