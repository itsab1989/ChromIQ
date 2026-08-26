"""A loaded patch set must be the one Generate lays out — in EVERY mode.

Loading an i1Profiler patch set (or a .ti1) and pressing "Generate Chart"
silently built a completely different chart: 2 patches in, 525 out, with no
dialog and only a line in the log. Two independent causes, both fixed here:

A. `_on_generate`'s preset branch was gated on `_current_mode() == "manual"`,
   but "Load patch set" lives in the tab HEADER, above the Guided/Manual stack,
   so it is offered in Guided too — where a beginner is. In Guided the branch
   was skipped entirely and `_preset_ti1_path` was not even cleared.

B. Binding the patch set lands the Profile-run bar on a run; on "New run" that
   is a change of run, which resets every per-target row to its factory value.
   targen's -e/-B go 0 -> 4, the snapshotted signature stops matching, and the
   patch set is dropped as though the user had asked for a fresh chart.
   `_layout_owned_by_build` is the shield the other two preset families already
   raise for exactly this (`_apply_prebuilt_preset`, `_apply_knut_preset`);
   the load path was the third family and was missed.

Measured against HEAD with the same driver:
    manual  bound=False -> fresh targen      (B: dropped)
    guided  bound=True  -> fresh targen      (A: branch skipped)
"""
import pathlib

import pytest


@pytest.fixture
def tab(qapp, tmp_path):
    from core.settings import AppSettings
    from ui.main_window import MainWindow

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("session_project", "")
    s.set("restore_last_session", False)
    w = MainWindow(s)
    qapp.processEvents()
    w._file_mgr.set_target_name("Patch Set Kept")
    w._file_mgr.project().current_run().ensure_dir()
    w._target_ctl.changed.emit()
    qapp.processEvents()
    yield w
    w.close()


def _arm(tc, tmp_path, *, sig_drifted, opted_in):
    """Put the tab in the state a completed patch-set load leaves behind."""
    ti1 = tmp_path / "loaded.ti1"
    ti1.write_text("PATCHES")
    tc._preset_ti1_path = ti1
    tc._preset_ti1_targen_sig = (("-e", 0, True),)
    if sig_drifted:
        tc._targen_signature = lambda: (("-e", 4, True),)
    else:
        tc._targen_signature = lambda: (("-e", 0, True),)
    if tc._override_targen_check is not None:
        tc._override_targen_check.setChecked(opted_in)
    return ti1


def _which_branch(tc, w, monkeypatch):
    took = []
    # No question is asked here any more: ticking "Edit patch recipe (override
    # preset)" already warns that the patches will be replaced, so a second
    # window at Generate time would interrupt a decision already made (Knut,
    # 4.1.3-beta.18). Nothing to answer — the fresh chart is simply built.
    monkeypatch.setattr(type(tc), "_generate_from_ti1",
                        lambda self, *a, **k: took.append("patch_set"))
    monkeypatch.setattr(tc._creator, "generate",
                        lambda *a, **k: took.append("fresh_targen"))
    monkeypatch.setattr(type(tc), "_confirm_displacing_results",
                        lambda self, *a, **k: True)
    monkeypatch.setattr(type(tc), "_handle_target_rename",
                        lambda self, *a, **k: True)
    tc._on_generate()
    return took[0] if took else "neither"


@pytest.mark.parametrize("mode", ["manual", "guided"])
def test_the_loaded_patch_set_is_used_in_every_mode(tab, tmp_path, monkeypatch,
                                                    mode):
    """Cause A. Guided is where a beginner is, and the loader is offered there."""
    w = tab
    tc = w._tab_chart
    monkeypatch.setattr(type(tc), "_current_mode", lambda self: mode)
    _arm(tc, tmp_path, sig_drifted=False, opted_in=False)

    assert _which_branch(tc, w, monkeypatch) == "patch_set", (
        f"in {mode} mode Generate ignored the patch set the user loaded and "
        "built a different chart instead")
    assert tc._preset_ti1_path is not None, "the patch set was dropped"


def test_a_drift_the_user_did_not_cause_does_not_drop_the_patch_set(
        tab, tmp_path, monkeypatch):
    """Cause B. The targen panel is LOCKED after a load, so a difference in its
    signature cannot be something the user did — it is the per-target reset."""
    tc = tab._tab_chart
    monkeypatch.setattr(type(tc), "_current_mode", lambda self: "manual")
    _arm(tc, tmp_path, sig_drifted=True, opted_in=False)

    assert _which_branch(tc, tab, monkeypatch) == "patch_set", (
        "a signature drift the user never asked for replaced their patch set "
        "with a fresh targen chart")


def test_ticking_the_override_still_gives_a_fresh_chart(tab, tmp_path,
                                                        monkeypatch):
    """The opt-in must keep working: unlock the recipe, change a knob, and you
    get the fresh chart you asked for. A fix that broke this would be worse
    than the bug."""
    tc = tab._tab_chart
    monkeypatch.setattr(type(tc), "_current_mode", lambda self: "manual")
    _arm(tc, tmp_path, sig_drifted=True, opted_in=True)

    assert _which_branch(tc, tab, monkeypatch) == "fresh_targen", (
        "the user unlocked the patch recipe and changed it, and ChromIQ still "
        "reused the old patch set")


def test_the_shield_is_raised_when_a_patch_set_is_bound(tab):
    """`_layout_owned_by_build` is what stops the per-target reset counting as
    user consent — the same shield the other two preset families raise."""
    import inspect

    from ui.tabs.tab_chart import TabChart

    src = inspect.getsource(TabChart._on_load_ti1)
    assert "_layout_owned_by_build = True" in src, (
        "the load path does not raise the shield the prebuilt and Knut preset "
        "families raise for this exact fault")
