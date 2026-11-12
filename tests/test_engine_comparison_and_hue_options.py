"""Two options around the new profile engine, and the corrected black texts
(Basti, 2026-11-11).

A. Preferences > Beta, directly under the engine switch: "Also build a
   colprof profile for comparison". Greyed out while the switch is off; on
   by default; off means no second colprof run and no
   ``colprof-comparison.icc`` for that build, and a comparison file left in
   the run by an earlier build is moved into ``old/`` so it is never taken
   for a comparison of the new profile.
B. Build Profile, shown only with the engine on: "Keep the original hue"
   (``BuildSettings.hue_rendering``, "argyll" = off, "kept"). Per target like
   the neighbouring engine rows; saved as a default and in a preset only
   while the engine is on, so a preset written with the engine off carries
   no value that would quietly apply later (per_target_settings.md, the
   2026-11-11 block awaiting confirmation).
C. The "Darkest black" tooltip and the Deepest log line say what was
   measured (research handover 15.5).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

from core.file_manager import COLPROF_COMPARISON_NAME  # noqa: E402
from core.settings import DEFAULTS  # noqa: E402
from workflow import engine_builder as eb  # noqa: E402
from workflow.profile_builder import ProfileParams  # noqa: E402

from tests.test_the_new_profile_engine_is_one_switch import (  # noqa: E402
    _Fake, _built_settings, _quiet_windows, _rgb_ti3,
    _run_with_ti3, _tab)

ROOT = Path(__file__).resolve().parent.parent
_FORBIDDEN = re.compile(r"research|agent|token|M-smooth|OKLab|x1-|huekeep|"
                        r"\ba\d{2,3}\b", re.I)


# ---------------------------------------------------------------------------
# A. the comparison option: the setting
# ---------------------------------------------------------------------------

def test_the_comparison_is_on_by_default_and_only_with_the_switch():
    assert DEFAULTS["profile_engine_colprof_comparison"] is True
    assert eb.colprof_comparison_setting(_Fake()) is True
    assert eb.colprof_comparison_wanted(_Fake()) is False      # switch off
    assert eb.colprof_comparison_wanted(
        _Fake(profile_engine_colprof_comparison=True)) is False
    assert eb.colprof_comparison_wanted(
        _Fake(profile_engine_beta=True)) is True
    assert eb.colprof_comparison_wanted(_Fake(
        profile_engine_beta=True,
        profile_engine_colprof_comparison=False)) is False
    # the forms an .ini store gives back
    for raw, want in (("false", False), ("true", True), ("0", False),
                      (None, True)):
        assert eb.colprof_comparison_wanted(_Fake(
            profile_engine_beta=True,
            profile_engine_colprof_comparison=raw)) is want, raw


# ---------------------------------------------------------------------------
# A. the comparison option: Preferences > Beta
# ---------------------------------------------------------------------------

def _dialog(qtbot, fake):
    from ui.dialogs.settings_dialog import SettingsDialog
    dlg = SettingsDialog(fake)
    qtbot.addWidget(dlg)
    return dlg


def test_the_option_stands_directly_under_the_switch(qtbot):
    dlg = _dialog(qtbot, _Fake(DEFAULTS))
    lay = dlg._beta_page.layout()
    items = [lay.itemAt(i) for i in range(lay.count())]
    eng = next(i for i, it in enumerate(items) if it.layout() is not None
               and any(it.layout().itemAt(k).widget()
                       is dlg._profile_engine_check
                       for k in range(it.layout().count())))
    assert items[eng + 1].widget() is dlg._colprof_comparison_cell
    # "Darkest black" stood next (eng + 2) until 2026-11-12; it is a Build
    # Profile row now (Basti), so nothing of it is left on this page.
    assert not hasattr(dlg, "_black_depth_cell")
    # indented, so it reads as part of the switch
    assert dlg._colprof_comparison_cell.layout().contentsMargins().left() > 0
    assert dlg._comparison_tip is not None


def test_greyed_out_with_the_switch_off_and_on_by_default_with_it_on(qtbot):
    fake = _Fake(DEFAULTS)
    dlg = _dialog(qtbot, fake)
    cb = dlg._colprof_comparison_check
    assert dlg._profile_engine_check.isChecked() is False
    assert cb.isEnabled() is False                 # greyed out
    assert not dlg._colprof_comparison_cell.isHidden()   # but visible
    assert cb.isChecked() is True
    dlg._profile_engine_check.setChecked(True)     # no consent: not a click
    assert cb.isEnabled() is True
    assert cb.isChecked() is True                  # on by default
    cb.setChecked(False)
    dlg._save_and_close()
    assert fake["profile_engine_beta"] is True
    assert fake["profile_engine_colprof_comparison"] is False
    again = _dialog(qtbot, fake)
    assert again._colprof_comparison_check.isChecked() is False
    assert again._colprof_comparison_check.isEnabled() is True
    again._profile_engine_check.setChecked(False)
    assert again._colprof_comparison_check.isEnabled() is False
    # the stored choice is kept while the switch is off
    assert again._colprof_comparison_check.isChecked() is False


# ---------------------------------------------------------------------------
# A. the comparison option: the build
# ---------------------------------------------------------------------------

def _engine_done(tmp_path, qtbot, monkeypatch, comparison):
    from ui.tabs import tab_profile as tp
    tab = _tab(tmp_path, profile_engine_beta=True,
               profile_engine_colprof_comparison=comparison)
    qtbot.addWidget(tab)
    run, ti3 = _run_with_ti3(tab, tmp_path)
    shown = _quiet_windows(monkeypatch, tab)
    icc = ti3.with_suffix(".icc")
    tab._active_params = ProfileParams(ti3_path=ti3)
    tab._engine_builder.reference_failed = ""
    tab._engine_builder.last_record = {"builder": "engine"}
    monkeypatch.setattr(tab._runner, "tool_is_installed", lambda _t: True)
    started: list = []

    def fake_build(self, p, on_line, on_finish):
        started.append(p)
        Path(str(p.ti3_path.with_suffix("")) + ".icc").write_bytes(
            b"colprof made this " * 100)
        on_finish(0)

    monkeypatch.setattr(tp.ProfileBuilder, "build", fake_build)
    return tab, run, ti3, icc, shown, started


def test_off_means_no_second_colprof_run_and_no_comparison_file(
        tmp_path, qtbot, monkeypatch):
    tab, run, ti3, icc, shown, started = _engine_done(
        tmp_path, qtbot, monkeypatch, comparison=False)
    icc.write_bytes(b"the engine made this " * 100)
    tab._on_engine_done(0)
    assert started == []
    assert not run.colprof_comparison_icc.exists()
    log = tab._log.toPlainText()
    assert "No comparison profile from ArgyllCMS colprof was built" in log
    assert "Profile saved" in log
    assert shown == [("result", str(icc))]
    rec = run.load_meta().profile_build
    assert rec["builder"] == "engine" and rec["colprof_comparison"] is False
    assert not (run.dir / "old").exists()          # nothing to move


def test_on_still_builds_it_and_says_so_in_the_record(
        tmp_path, qtbot, monkeypatch):
    tab, run, ti3, icc, shown, started = _engine_done(
        tmp_path, qtbot, monkeypatch, comparison=True)
    icc.write_bytes(b"the engine made this " * 100)
    tab._on_engine_done(0)
    assert len(started) == 1
    assert run.colprof_comparison_icc.read_bytes().startswith(
        b"colprof made this")
    assert run.load_meta().profile_build["colprof_comparison"] is True


def test_an_older_comparison_goes_with_its_profile_when_the_option_is_off(
        tmp_path, qtbot, monkeypatch):
    """The usual case: the archive at the start of the build moves the old
    comparison together with the profile it was built beside."""
    tab, run, ti3, icc, shown, started = _engine_done(
        tmp_path, qtbot, monkeypatch, comparison=False)
    icc.write_bytes(b"old profile " * 100)
    run.colprof_comparison_icc.write_bytes(b"old comparison " * 100)
    params = tab._active_params
    tab._archive_the_profile_being_replaced(params)
    assert not run.colprof_comparison_icc.exists()
    icc.write_bytes(b"the engine made this " * 100)
    tab._on_engine_done(0)
    assert started == [] and not run.colprof_comparison_icc.exists()
    old = sorted(p.name for p in (run.dir / "old").rglob("*.icc"))
    assert old == ["Arch.icc", COLPROF_COMPARISON_NAME]


def test_a_comparison_without_its_profile_is_moved_out_too(
        tmp_path, qtbot, monkeypatch):
    """A comparison file with no older profile beside it (the profile was
    removed by hand) cannot belong to the new profile either."""
    tab, run, ti3, icc, shown, started = _engine_done(
        tmp_path, qtbot, monkeypatch, comparison=False)
    run.colprof_comparison_icc.write_bytes(b"orphan comparison " * 100)
    tab._archive_the_profile_being_replaced(tab._active_params)
    assert run.colprof_comparison_icc.exists()     # nothing to travel with
    icc.write_bytes(b"the engine made this " * 100)
    tab._on_engine_done(0)
    assert not run.colprof_comparison_icc.exists()
    moved = list((run.dir / "old").rglob(COLPROF_COMPARISON_NAME))
    assert len(moved) == 1
    assert moved[0].read_bytes().startswith(b"orphan comparison")
    assert icc.read_bytes().startswith(b"the engine made this")
    log = tab._log.toPlainText()
    assert "does not belong to the new profile" in log
    assert str(moved[0].parent) in log


def test_a_comparison_without_its_profile_is_kept_when_the_option_is_on(
        tmp_path, qtbot, monkeypatch):
    """Review 2026-11-11 (F3): with the option ON the new comparison was
    moved in after DELETING the one already there (the profile it belonged
    to had been removed by hand, so the archive at the start of the build
    left it). It goes into ``old/`` instead, as with the option off."""
    tab, run, ti3, icc, shown, started = _engine_done(
        tmp_path, qtbot, monkeypatch, comparison=True)
    run.colprof_comparison_icc.write_bytes(b"orphan comparison " * 100)
    tab._archive_the_profile_being_replaced(tab._active_params)
    icc.write_bytes(b"the engine made this " * 100)
    tab._on_engine_done(0)
    assert len(started) == 1
    assert run.colprof_comparison_icc.read_bytes().startswith(
        b"colprof made this")
    moved = list((run.dir / "old").rglob(COLPROF_COMPARISON_NAME))
    assert len(moved) == 1
    assert moved[0].read_bytes().startswith(b"orphan comparison")
    assert str(moved[0].parent) in tab._log.toPlainText()


def test_a_failed_build_with_the_option_off_puts_the_old_pair_back(
        tmp_path, qtbot, monkeypatch):
    tab, run, ti3, icc, shown, started = _engine_done(
        tmp_path, qtbot, monkeypatch, comparison=False)
    icc.write_bytes(b"old profile " * 100)
    run.colprof_comparison_icc.write_bytes(b"old comparison " * 100)
    tab._archive_the_profile_being_replaced(tab._active_params)
    tab._engine_builder._last_error = "the model could not be fitted"
    tab._on_engine_done(1)
    assert icc.read_bytes().startswith(b"old profile")
    assert run.colprof_comparison_icc.read_bytes().startswith(
        b"old comparison")


# ---------------------------------------------------------------------------
# B. "Keep the original hue": the build
# ---------------------------------------------------------------------------

def test_the_hue_reaches_the_engine_settings(monkeypatch, tmp_path):
    s = _built_settings(monkeypatch, tmp_path,
                        _Fake(profile_engine_beta=True))
    assert s.hue_rendering == "argyll"
    s = _built_settings(monkeypatch, tmp_path,
                        _Fake(profile_engine_beta=True),
                        hue_rendering="kept")
    assert s.hue_rendering == "kept"
    from workflow.profile_engine.builder import effective_engine_candidates
    assert "x1-huekeep" in effective_engine_candidates(s)
    assert ProfileParams(ti3_path=Path("x.ti3")).hue_rendering == "argyll"


def test_the_record_names_the_hue_choice():
    from workflow.profile_engine import BuildSettings
    rec = eb.EngineLines(lambda _l: None).record(
        BuildSettings(hue_rendering="kept"))
    assert rec["hue_rendering"] == "kept"


def test_the_comparison_profile_is_built_without_the_hue_option(
        tmp_path, qtbot, monkeypatch):
    tab, run, ti3, icc, shown, started = _engine_done(
        tmp_path, qtbot, monkeypatch, comparison=True)
    import dataclasses
    tab._active_params = dataclasses.replace(tab._active_params,
                                             hue_rendering="kept")
    icc.write_bytes(b"the engine made this " * 100)
    tab._on_engine_done(0)
    assert started[0].hue_rendering == "argyll"


# ---------------------------------------------------------------------------
# B. "Keep the original hue": the Build Profile tab
# ---------------------------------------------------------------------------

def test_the_hue_box_is_an_engine_row(tmp_path, qtbot):
    tab = _tab(tmp_path)                            # engine off
    qtbot.addWidget(tab)
    assert tab._m_hue_cb.parent() is not None
    assert tab._m_engine_rows_widget.isAncestorOf(tab._m_hue_cb)
    assert tab._m_engine_rows_widget.isAncestorOf(tab._m_hue_tip)
    assert tab._m_engine_rows_widget.isHidden()
    assert tab._m_hue_cb.isChecked() is False       # off by default
    tab._settings.set("profile_engine_beta", True)
    tab._refresh_engine_rows()
    assert not tab._m_engine_rows_widget.isHidden()
    assert tab._m_hue_cb.text() == "Keep the original hue"


def test_the_hue_reaches_the_params_only_with_the_engine_on(tmp_path, qtbot):
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    assert tab._collect_manual_profile().hue_rendering == "argyll"
    tab._m_hue_cb.setChecked(True)
    assert tab._collect_manual_profile().hue_rendering == "kept"
    tab._settings.set("profile_engine_beta", False)
    assert tab._collect_manual_profile().hue_rendering == "argyll"


def test_a_preset_carries_the_hue_only_when_saved_with_the_engine_on(
        tmp_path, qtbot):
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    tab._m_hue_cb.setChecked(True)
    on = tab._m_collect_preset_data()
    assert on["hue_rendering"] == "kept"
    tab._m_hue_cb.setChecked(False)
    assert tab._m_collect_preset_data()["hue_rendering"] == "argyll"
    tab._m_apply_preset_data(on)
    assert tab._m_hue_cb.isChecked() is True
    # the engine off: the box is hidden, so the preset says nothing
    tab._settings.set("profile_engine_beta", False)
    off = tab._m_collect_preset_data()
    assert "hue_rendering" not in off
    # ...and a preset that says nothing loads as off, so a value nobody
    # could see never applies later
    tab._settings.set("profile_engine_beta", True)
    assert tab._m_hue_cb.isChecked() is True
    tab._m_apply_preset_data(off)
    assert tab._m_hue_cb.isChecked() is False
    # a preset from before the option, likewise
    tab._m_hue_cb.setChecked(True)
    tab._m_apply_preset_data({"quality": "m"})
    assert tab._m_hue_cb.isChecked() is False


def test_saved_presets_round_trip_through_the_preset_store(tmp_path, qtbot,
                                                           monkeypatch):
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    store: dict = {}
    monkeypatch.setattr(tab, "_m_load_presets", lambda: dict(store))
    tab._m_hue_cb.setChecked(True)
    store["hue on"] = tab._m_collect_preset_data()
    tab._settings.set("profile_engine_beta", False)
    store["saved with the engine off"] = tab._m_collect_preset_data()
    tab._settings.set("profile_engine_beta", True)
    tab._m_populate_preset_combo(store)
    combo = tab._m_preset_combo
    tab._m_hue_cb.setChecked(False)
    combo.setCurrentIndex(combo.findData("hue on"))
    tab._on_m_preset_selected(combo.currentIndex())
    assert tab._m_hue_cb.isChecked() is True
    combo.setCurrentIndex(combo.findData("saved with the engine off"))
    tab._on_m_preset_selected(combo.currentIndex())
    assert tab._m_hue_cb.isChecked() is False


def test_save_as_default_takes_the_hue_only_with_the_engine_on(tmp_path,
                                                               qtbot):
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    tab._stack.setCurrentIndex(1)                   # Manual
    assert (tab._settings.get("manual2_colprof_hue", "argyll")
            or "argyll") == "argyll"
    tab._m_hue_cb.setChecked(True)
    tab._on_save_defaults()
    assert tab._settings.get("manual2_colprof_hue") == "kept"
    tab._m_hue_cb.setChecked(False)
    tab._on_m_preset_selected(0)                    # "Default settings"
    assert tab._m_hue_cb.isChecked() is True
    # engine off: Save as default leaves the saved hue default alone
    tab._settings.set("profile_engine_beta", False)
    tab._m_hue_cb.setChecked(False)
    tab._on_save_defaults()
    assert tab._settings.get("manual2_colprof_hue") == "kept"


def test_restore_defaults_covers_the_hue(tmp_path, qtbot):
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    tab._m_hue_cb.setChecked(True)
    tab._restore_defaults()
    assert tab._m_hue_cb.isChecked() is False       # factory: off
    tab._settings.set("manual2_colprof_hue", "kept")
    tab._restore_defaults()
    assert tab._m_hue_cb.isChecked() is True


def test_the_target_keeps_its_hue_with_the_engine_on_and_off(tmp_path,
                                                             qtbot):
    """Per target like the other engine rows (§5): written with the
    target's settings whatever the switch says, and loaded back."""
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    run, _ti3 = _run_with_ti3(tab, tmp_path)
    tab._m_hue_cb.setChecked(True)
    assert tab.save_target_settings(store=run) is True
    assert run.load_meta().profile_settings["hue_rendering"] == "kept"
    tab._m_hue_cb.setChecked(False)
    tab._m_apply_preset_data(run.load_meta().profile_settings)
    assert tab._m_hue_cb.isChecked() is True
    # the engine switched off: the target's choice is not lost by a write
    tab._settings.set("profile_engine_beta", False)
    tab._profile_written_cache().clear()
    tab.save_target_settings(store=run)
    assert run.load_meta().profile_settings["hue_rendering"] == "kept"
    # and a target stored before the option existed opens with it off
    meta = run.load_meta()
    meta.profile_settings = {k: v for k, v in meta.profile_settings.items()
                             if k != "hue_rendering"}
    run.save_meta(meta)
    tab._m_apply_preset_data(run.load_meta().profile_settings)
    assert tab._m_hue_cb.isChecked() is False


def test_the_spec_records_the_hue_rule_as_awaiting_confirmation():
    spec = (ROOT / "docs/design/per_target_settings.md").read_text("utf-8")
    i = spec.index("Keep the original hue")
    block = spec[spec.rindex("### ", 0, i):]
    block = block[:block.index("\n### ", 1)] if "\n### " in block[1:] \
        else block
    assert "Awaiting confirmation" in block.splitlines()[0]
    assert "**Confirmed by:** *nobody yet.*" in block
    assert "manual2_colprof_hue" in block and "hue_rendering" in block


# ---------------------------------------------------------------------------
# B. the build log
# ---------------------------------------------------------------------------

def test_the_hue_lines_reach_the_window_in_plain_words():
    from workflow.profile_engine import hue_keep as HK
    shown: list = []
    lines = eb.EngineLines(shown.append)
    info = {"rounds": 8, "pinned": 33, "moved_median": 3.6,
            "moved_p95": 29.4, "miss_median": 0.2, "miss_p95": 5.5}
    lines("88% · ~5s left · " + HK.progress_line("B2A0", info))
    lines(HK.NOT_RGB_LINE)
    assert shown[0].startswith("88% · ~5s left · Keep the original hue: ")
    assert "Perceptual" in shown[0]
    assert "RGB printers only" in shown[1]
    for text in shown:
        assert not _FORBIDDEN.search(text), text


# ---------------------------------------------------------------------------
# C. the black texts, and the texts that promised the comparison
# ---------------------------------------------------------------------------

def test_the_darkest_black_tooltip_says_what_was_measured():
    # the tooltip moved with the option into the Build Profile tab
    # (2026-11-12); its measured facts are kept word for word
    src = (ROOT / "ui/tabs/tab_profile.py").read_text("utf-8")
    i = src.index('tr("Darkest black"),')
    tip = src[i:src.index("min_width=680", i)]
    flat = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', tip))
    assert "L* 7.3 to L* 5.2" not in flat
    assert "violet" not in flat
    assert "between about 1 and 2 L*" in flat
    assert "darkest four steps" in flat           # Neutral, without BPC
    assert "no profile can prevent it" in flat    # BPC carries the tint
    assert "with either choice" in flat
    assert "has not been confirmed by a measured print yet" in flat
    assert "Only the Relative Colorimetric and Absolute Colorimetric" in flat
    assert "Only RGB printers with a tinted black" in flat
    assert "the same black" in flat               # the warning stays
    assert "—" not in flat


def test_the_deepest_line_keeps_the_warning():
    shown: list = []
    lines = eb.EngineLines(shown.append)
    lines("Colorimetric table: deepest black deepest (research a88: printer "
          "black L* 4.4 a* 2.1 b* -6.3; darkest printable neutral L* 7.3 "
          "a* 0.1 b* -0.4; 212 nodes).")
    text = shown[0]
    assert "black point compensation" in text
    assert "without it, the darkest few steps print as the same black" in text
    assert "instead of stopping at" not in text
    assert not _FORBIDDEN.search(text) and "—" not in text


def test_the_engine_texts_name_the_option_and_no_longer_promise_the_file():
    src = (ROOT / "ui/dialogs/settings_dialog.py").read_text("utf-8")
    label = "Also build a colprof profile for comparison"
    flat = re.sub(r'"\s*\n\s*"', "", src)
    assert flat.count(label) >= 3         # the box, the tooltip, the window
    assert ("The profile from colprof is kept as well. After each "
            "build") not in flat
    assert "Without it a build is clearly quicker" in flat
    assert "each build is clearly quicker" in flat


def test_the_new_texts_carry_no_internal_names_and_no_em_dash():
    import ast
    want = ("Keep the original hue", "colprof profile for comparison",
            "Also build a colprof profile for comparison", "Darkest black",
            "No comparison profile from ArgyllCMS colprof",
            "An older comparison profile")
    found = []
    for rel in ("ui/dialogs/settings_dialog.py", "ui/tabs/tab_profile.py",
                "workflow/engine_builder.py"):
        tree = ast.parse((ROOT / rel).read_text("utf-8"))
        for n in ast.walk(tree):
            if (isinstance(n, ast.Call) and getattr(n.func, "id", "") == "tr"
                    and n.args and isinstance(n.args[0], ast.Constant)):
                text = n.args[0].value
                if (text.startswith(want) or "Keep the original hue" in text
                        or "colprof profile for comparison" in text):
                    found.append(text)
    assert len(found) >= 10, len(found)
    for text in found:
        assert "—" not in text, text[:80]
        assert not _FORBIDDEN.search(text), text[:120]
