"""The new profile engine in the app: one switch, and what stands around it.

2026-11-10, the app shape decided for the engine (Basti):

* Preferences > Beta holds ONE switch, off by default. Off is stock colprof.
  On is the engine's Maximum accuracy build. The Fast / Bit-exact / Maximum
  accuracy picker is gone, and stored settings are migrated.
* A black option (Neutral, Deepest) appears only while the switch is on.
* A packaged app ignores the engine's development environment variables.
* When colprof cannot give the engine its reference rendering, the build
  goes to stock colprof and says so. Never the engine's own rendering.
* Every engine build records which internal switches were on and which
  reported acting, in ``chromiq.log`` and the run's ``meta.json``, and none
  of those names reaches the window.
* colprof's own profile is kept beside the engine's, role-named, and never
  answers for the run.
* With the switch on, illuminant, observer and brightener compensation are
  built by the engine itself (Basti: "our engine should be able to use the
  same options that colprof allows").
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import QSettings  # noqa: E402

from core import engine_env  # noqa: E402
from core.file_manager import (COLPROF_COMPARISON_NAME, Project, Run,  # noqa: E402
                               RunMeta)
from core.settings import DEFAULTS, SETTINGS_SCHEMA, AppSettings  # noqa: E402
from workflow import engine_builder as eb  # noqa: E402
from workflow.profile_builder import ProfileParams  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class _Fake(dict):
    """A settings stand-in with the two methods the code under test uses."""

    def get(self, k, d=None):
        return dict.get(self, k, d)

    def set(self, k, v):
        self[k] = v


def _rgb_ti3(path: Path) -> Path:
    from tests.test_profile_engine import write_synth_ti3
    return write_synth_ti3(path, "iRGB", ["RGB_R", "RGB_G", "RGB_B"], True)


def _multi_ink_ti3(path: Path) -> Path:
    path.write_text('CTI3\nCOLOR_REP "CMYKOG_XYZ"\n', encoding="utf-8")
    return path


def _store(tmp_path, **stored) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    for k, v in stored.items():
        s._qs.setValue(k, v)
    return s


def _tab(tmp_path, **prefs):
    from tests.test_engine_v2_options import _tab as make
    return make(tmp_path, **prefs)


# ---------------------------------------------------------------------------
# A. one switch, off by default; the picker is gone
# ---------------------------------------------------------------------------

def test_the_switch_is_off_by_default_and_the_picker_has_no_setting():
    assert DEFAULTS["profile_engine_beta"] is False
    assert DEFAULTS["profile_engine_black_depth"] == "neutral"
    assert "gammap_mode" not in DEFAULTS
    assert SETTINGS_SCHEMA >= 32


def test_preferences_has_no_mode_picker_any_more(qtbot):
    from ui.dialogs.settings_dialog import SettingsDialog
    dlg = SettingsDialog(_Fake(DEFAULTS))
    qtbot.addWidget(dlg)
    assert not hasattr(dlg, "_gammap_mode_combo")
    assert not hasattr(dlg, "_gammap_mode_cell")
    src = (ROOT / "ui/dialogs/settings_dialog.py").read_text(encoding="utf-8")
    for gone in ('tr("Bit-exact")', 'tr("Fast")', 'tr("Maximum accuracy")',
                 "gammap_mode"):
        assert gone not in src, gone
    dlg._save_and_close()
    assert "gammap_mode" not in dlg._settings


def test_the_black_option_shows_only_with_the_switch_on_and_is_saved(qtbot):
    from ui.dialogs.settings_dialog import SettingsDialog
    fake = _Fake(DEFAULTS)
    dlg = SettingsDialog(fake)
    qtbot.addWidget(dlg)
    assert dlg._profile_engine_check.isChecked() is False
    assert dlg._black_depth_cell.isHidden()
    dlg._profile_engine_check.setChecked(True)       # no consent: not a click
    assert not dlg._black_depth_cell.isHidden()
    assert [dlg._black_depth_combo.itemData(i)
            for i in range(dlg._black_depth_combo.count())] == [
                "neutral", "deepest"]
    assert dlg._black_depth_combo.currentData() == "neutral"
    dlg._black_depth_combo.setCurrentIndex(
        dlg._black_depth_combo.findData("deepest"))
    dlg._save_and_close()
    assert fake["profile_engine_beta"] is True
    assert fake["profile_engine_black_depth"] == "deepest"
    again = SettingsDialog(fake)
    qtbot.addWidget(again)
    assert again._black_depth_combo.currentData() == "deepest"
    assert not again._black_depth_cell.isHidden()
    again._profile_engine_check.setChecked(False)
    assert again._black_depth_cell.isHidden()


def test_an_unknown_stored_black_depth_reads_as_neutral():
    assert eb.black_depth_setting(_Fake()) == "neutral"
    assert eb.black_depth_setting(
        _Fake(profile_engine_black_depth="balanced")) == "neutral"
    assert eb.black_depth_setting(
        _Fake(profile_engine_black_depth=" Deepest ")) == "deepest"


# ---------------------------------------------------------------------------
# A. migration of stored settings
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("stored, on_after", [
    (dict(profile_engine_beta="true", gammap_mode="accurate"), True),
    (dict(profile_engine_beta="true", gammap_mode="fast"), False),
    (dict(profile_engine_beta="true", gammap_mode="argyll"), False),
    (dict(profile_engine_beta="true"), False),        # the old default, Fast
    (dict(profile_engine_beta="false", gammap_mode="accurate"), False),
    (dict(gammap_mode="accurate"), False),
    (dict(gammap_mode="nonsense", profile_engine_beta="true"), False),
    ({}, False),
])
def test_stored_settings_become_the_one_switch(tmp_path, stored, on_after):
    s = _store(tmp_path, settings_schema=31, **stored)
    s.migrate()
    assert bool(s.get("profile_engine_beta", False)) is on_after
    assert s._qs.value("gammap_mode", None) is None
    assert int(s._qs.value("settings_schema")) == SETTINGS_SCHEMA


def test_the_migration_runs_once_and_keeps_a_later_choice(tmp_path):
    s = _store(tmp_path, settings_schema=31, profile_engine_beta="true",
               gammap_mode="fast")
    s.migrate()
    assert s.get("profile_engine_beta") is False
    s.set("profile_engine_beta", True)               # the user switches it on
    s.migrate()
    assert s.get("profile_engine_beta") is True


# ---------------------------------------------------------------------------
# A. which builder runs
# ---------------------------------------------------------------------------

def test_off_is_colprof_and_on_is_the_engine(tmp_path):
    p = ProfileParams(ti3_path=_rgb_ti3(tmp_path / "s.ti3"))
    assert eb.choose_builder(_Fake(), p) == ("colprof", "")
    assert eb.choose_builder(_Fake(profile_engine_beta=True), p) == (
        "engine", "")
    # a leftover of the old picker changes nothing
    assert eb.choose_builder(
        _Fake(profile_engine_beta=True, gammap_mode="argyll"), p) == (
            "engine", "")
    assert eb.choose_builder(_Fake(gammap_mode="accurate"), p) == (
        "colprof", "")


def test_a_multi_ink_measurement_needs_the_switch(tmp_path):
    p = ProfileParams(ti3_path=_multi_ink_ti3(tmp_path / "og.ti3"))
    assert eb.choose_builder(_Fake(), p) == ("blocked", "")
    which, why = eb.choose_builder(_Fake(profile_engine_beta=True), p)
    assert which == "engine" and why


@pytest.mark.parametrize("kw", [dict(illuminant="D65"),
                                dict(observer="1964_10"),
                                dict(fwa_enabled=True),
                                dict(extra_args="-i D65"),
                                dict(extra_args="-o 1964_10"),
                                dict(extra_args="-f")])
def test_illuminant_observer_and_fwa_are_built_by_the_engine(tmp_path, kw):
    """Basti, 2026-11-10: the engine uses the same options colprof allows.
    No hand-over to colprof and no extra line for these."""
    p = ProfileParams(ti3_path=_rgb_ti3(tmp_path / "s.ti3"), **kw)
    assert eb.choose_builder(_Fake(profile_engine_beta=True), p) == (
        "engine", "")


def test_an_unknown_extra_flag_still_goes_to_colprof(tmp_path):
    p = ProfileParams(ti3_path=_rgb_ti3(tmp_path / "s.ti3"),
                      extra_args="-g x.gam")
    which, why = eb.choose_builder(_Fake(profile_engine_beta=True), p)
    assert which == "colprof" and "-g" in why


def test_the_tab_asks_the_one_chooser(tmp_path, qtbot):
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    p = ProfileParams(ti3_path=_rgb_ti3(tmp_path / "s.ti3"))
    assert tab._choose_engine(p) == ("engine", "")
    assert tab._accurate_engine_active() is True
    tab._settings.set("profile_engine_beta", False)
    assert tab._choose_engine(p) == ("colprof", "")
    assert tab._accurate_engine_active() is False


class _NoThread:
    """Stands in for the build thread: keeps what it was given."""
    made: list = []

    class _Sig:
        def connect(self, *_a):
            pass

    def __init__(self, ti3, out, settings):
        self.settings = settings
        self.line = self.done = self.finished = self._Sig()
        self.reference_failed = ""
        self.record = {}
        _NoThread.made.append(self)

    def start(self):
        pass

    def isRunning(self):          # noqa: N802 - Qt's name
        return False

    def deleteLater(self):        # noqa: N802
        pass


def _built_settings(monkeypatch, tmp_path, app_settings, **params):
    _NoThread.made.clear()
    monkeypatch.setattr(eb, "_EngineThread", _NoThread)
    b = eb.EngineProfileBuilder(app_settings)
    b.build(ProfileParams(ti3_path=_rgb_ti3(tmp_path / "s.ti3"), **params),
            on_line=lambda _l: None, on_finish=lambda _c: None)
    eb.EngineProfileBuilder._RUNNING.discard(b)
    assert len(_NoThread.made) == 1
    return _NoThread.made[0].settings


def test_the_app_builds_maximum_accuracy_with_the_default_thread_count(
        monkeypatch, tmp_path):
    monkeypatch.delenv("CHROMIQ_ENGINE_NEXT", raising=False)
    s = _built_settings(monkeypatch, tmp_path, _Fake(
        profile_engine_beta=True, argyll_bin_path="/nowhere"))
    assert s.gammap_mode == "accurate"
    assert s.engine_workers == 0
    assert s.black_depth == "neutral"
    assert s.engine_candidates == frozenset()
    assert str(s.argyll_bin) == "/nowhere"
    # whatever an old store still says
    s = _built_settings(monkeypatch, tmp_path, _Fake(
        profile_engine_beta=True, gammap_mode="fast",
        profile_engine_black_depth="deepest"))
    assert s.gammap_mode == "accurate" and s.black_depth == "deepest"
    from workflow.profile_engine.builder import effective_engine_candidates
    assert "a88-black-deepest" in effective_engine_candidates(s)
    # and with no settings object at all
    assert _built_settings(monkeypatch, tmp_path, None).gammap_mode == \
        "accurate"


def test_the_engine_gets_illuminant_observer_and_fwa(monkeypatch, tmp_path):
    s = _built_settings(monkeypatch, tmp_path,
                        _Fake(profile_engine_beta=True),
                        illuminant="D65", observer="1964_10")
    assert (s.illuminant, s.observer) == ("D65", "1964_10")


# ---------------------------------------------------------------------------
# B1. a packaged app ignores the development variables
# ---------------------------------------------------------------------------

def _names_the_engine_reads() -> set:
    names = set()
    files = list((ROOT / "workflow/profile_engine").rglob("*.py"))
    files.append(ROOT / "workflow/engine_builder.py")
    for f in files:
        text = f.read_text(encoding="utf-8")
        for m in re.finditer(r"environ(?:\.get\(|\[)\s*\n?\s*[\"']"
                             r"(CHROMIQ_[A-Z0-9_]+)", text):
            names.add(m.group(1))
        for m in re.finditer(r"^_ENV\w*\s*=\s*[\"'](CHROMIQ_[A-Z0-9_]+)",
                             text, re.M):
            names.add(m.group(1))
    return names


def test_every_variable_the_engine_reads_is_a_known_override():
    names = _names_the_engine_reads()
    assert len(names) >= 50, sorted(names)           # the scan still works
    assert "CHROMIQ_ENGINE_THREADS" in names
    unknown = sorted(n for n in names if not engine_env.is_engine_override(n))
    assert not unknown, (
        "the engine reads variables a packaged app would not ignore; add "
        f"them to core/engine_env.py: {unknown}")


@pytest.mark.parametrize("name", [
    "CHROMIQ_SETTINGS_FILE", "CHROMIQ_PRESETS_DIR", "CHROMIQ_LOG_DIR",
    "CHROMIQ_DEMO_CACHE", "CHROMIQ_NO_KEEP_AWAKE", "CHROMIQ_SELFTEST",
    "CHROMIQ_NO_AUDIO_KEEPALIVE", "CHROMIQ_OUTPUT_ROOT", "PATH"])
def test_the_apps_own_variables_are_never_taken_for_overrides(name):
    assert not engine_env.is_engine_override(name)


_LEFTOVERS = {"CHROMIQ_A51_MU": "9", "CHROMIQ_A88": "1,2",
              "CHROMIQ_A84_KEEP": "1", "CHROMIQ_A21_FIT_CACHE": "/x",
              "CHROMIQ_ENGINE_NEXT": "a19-extrap",
              "CHROMIQ_ENGINE_THREADS": "3", "CHROMIQ_GAMMAP": "/y"}


def test_from_source_nothing_is_removed(monkeypatch):
    monkeypatch.delattr("sys.frozen", raising=False)
    env = dict(_LEFTOVERS, CHROMIQ_SETTINGS_FILE="/s.ini")
    assert engine_env.ignore_engine_overrides_when_frozen(env) == []
    assert env == dict(_LEFTOVERS, CHROMIQ_SETTINGS_FILE="/s.ini")


def test_a_packaged_app_removes_every_override_and_nothing_else(monkeypatch):
    monkeypatch.setattr("sys.frozen", True, raising=False)
    env = dict(_LEFTOVERS, CHROMIQ_SETTINGS_FILE="/s.ini", HOME="/h")
    removed = engine_env.ignore_engine_overrides_when_frozen(env)
    assert removed == sorted(_LEFTOVERS)
    assert env == {"CHROMIQ_SETTINGS_FILE": "/s.ini", "HOME": "/h"}
    assert engine_env.ignore_engine_overrides_when_frozen(env) == []


def test_a_packaged_build_never_reads_the_extra_switch_list(
        monkeypatch, tmp_path):
    """The process environment is cleaned at the door every build passes."""
    for k, v in _LEFTOVERS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr("sys.frozen", True, raising=False)
    s = _built_settings(monkeypatch, tmp_path, _Fake(profile_engine_beta=True))
    assert s.engine_candidates == frozenset()
    assert not [k for k in os.environ if engine_env.is_engine_override(k)]
    from workflow.profile_engine import parallel
    assert parallel.worker_count() == parallel.default_workers()


def test_from_source_the_thread_override_keeps_working(monkeypatch, tmp_path):
    """The suite's own CHROMIQ_ENGINE_THREADS=1, and a research battery's."""
    monkeypatch.delattr("sys.frozen", raising=False)
    monkeypatch.setenv("CHROMIQ_ENGINE_THREADS", "3")
    monkeypatch.setenv("CHROMIQ_ENGINE_NEXT", "a19-extrap")
    s = _built_settings(monkeypatch, tmp_path, _Fake(profile_engine_beta=True))
    assert os.environ["CHROMIQ_ENGINE_THREADS"] == "3"
    from workflow.profile_engine import parallel
    assert parallel.worker_count() == 3
    assert s.engine_candidates == frozenset({"a19-extrap"})


def test_main_cleans_the_environment_before_the_engine_can_be_imported():
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    call = src.index("ignore_engine_overrides_when_frozen()")
    assert call < src.index("from PyQt6.QtGui import QIcon")
    assert call < src.index("def main()")


# ---------------------------------------------------------------------------
# B2 / B3 / C. the engine's lines: what is shown, kept, and what stops it
# ---------------------------------------------------------------------------

_A88_FIRES = ("Colorimetric table: deepest black deepest (research a88: "
              "printer black L* 4.4 a* 2.1 b* -6.3; darkest printable "
              "neutral L* 7.3 a* 0.1 b* -0.4; 212 nodes).")
_A88_IDLE = ("Colorimetric table: deepest black deepest (research a88: "
             "printer black L* 3.1 a* 0.2 b* 0.1; darkest printable neutral "
             "L* 3.4 a* 0.1 b* 0.0; 0 nodes, not needed).")
_A88_NONE = ("Colorimetric table: deepest black deepest (research a88: "
             "printer black L* 3.1 a* 0.2 b* 0.1; darkest printable neutral "
             "none; 0 nodes, not needed).")

_INTERNAL = re.compile(r"research|agent|\ba\d{2,3}[a-z]?\b|\ba\d{2,3}-|"
                       r"b2a33|gpsel|rgbcol|knutdark|token|candidate", re.I)


def test_a_line_that_names_a_switch_is_kept_but_not_shown():
    shown: list = []
    lines = eb.EngineLines(shown.append)
    lines("2% · Reading the measurement…")
    lines("8% · Candidate pipeline active: a25-oog, a84-warmblack, b2a33s, "
          "rgbcol.")
    lines("20% · ~1 min left · Colorimetric table: colprof's inverse grid "
          "and CAM clip (research a58-purecolprof).")
    lines("30% · Ink fold check (a74-foldmeas): measured 2.4.")
    lines("31% · a86-knutdark (B2A0): the oracle's A2B says 3 steps merge.")
    lines("40% · Gamut mapping: smoothing…")
    assert shown == ["2% · Reading the measurement…",
                     "40% · Gamut mapping: smoothing…"]
    assert lines.switches_on == ["a25-oog", "a84-warmblack", "b2a33s",
                                 "rgbcol"]
    assert [r["switch"] for r in lines.reported] == [
        "a58-purecolprof", "a74-foldmeas", "a86-knutdark"]
    assert "CAM clip" in lines.reported[0]["line"]
    rec = lines.record(eb.BuildSettings(black_depth="deepest"))
    assert rec["builder"] == "engine" and rec["black_depth"] == "deepest"
    assert rec["switches_on"] == lines.switches_on
    assert "black_depth='deepest'" in rec["settings"]


def test_ordinary_lines_pass_through_untouched():
    shown: list = []
    lines = eb.EngineLines(shown.append)
    for msg in ("Computing colorimetry from the spectral data…",
                "Black ink limited to 90%.",
                "62% · ~20s left · Gamut mapping: fine-tuning 3/8…",
                "Averaged 4 repeated patch(es) (8 extra readings) before "
                "the fit."):
        lines(msg)
    assert len(shown) == 4 and not lines.reported


@pytest.mark.parametrize("raw, changed, has_neutral", [
    (_A88_FIRES, True, True), (_A88_IDLE, False, True),
    (_A88_NONE, False, False)])
def test_the_deepest_black_report_is_reworded_for_the_user(
        raw, changed, has_neutral):
    shown: list = []
    lines = eb.EngineLines(shown.append)
    lines("76% · ~10s left · " + raw)
    assert len(shown) == 1
    text = shown[0]
    assert text.startswith("76% · ~10s left · Deepest black:")
    assert not _INTERNAL.search(text.split(" · ", 2)[2]), text
    assert "L* " in text and "—" not in text
    assert lines.dark_end["changed_the_table"] is changed
    assert (lines.dark_end["darkest_neutral_lab"] is not None) is has_neutral
    if changed:
        assert lines.dark_end["printer_black_lab"] == [4.4, 2.1, -6.3]
        assert lines.dark_end["darkest_neutral_lab"] == [7.3, 0.1, -0.4]
        assert "black point compensation" in text
    else:
        assert "same as with Neutral" in text
    assert lines.reported[0]["switch"] == "a88-black-deepest"


def test_the_engine_still_words_its_deepest_report_the_way_we_read_it():
    """The rewording hangs on the engine's own sentence. If research changes
    it, this fails here instead of a raw line reaching a user."""
    src = (ROOT / "workflow/profile_engine/builder.py").read_text("utf-8")
    for part in ('"Colorimetric table: deepest black "', "(research a88: ",
                 '"printer black L* "', "darkest printable ", "; {_a88i['nodes']} nodes",
                 "', not needed'"):
        assert part in src, part
    assert '"Candidate pipeline active: "' in src
    gm = (ROOT / "workflow/profile_engine/gamut_map.py").read_text("utf-8")
    assert "Using the engine's own rendering (" in gm


def test_a_missing_colprof_reference_stops_a_standard_build():
    shown: list = []
    lines = eb.EngineLines(shown.append)
    lines("10% · Fitting the printer model…")
    with pytest.raises(eb.ColprofReferenceFailed) as exc:
        lines("26% · Using the engine's own rendering (colprof oracle "
              "failed: bad file).")
    # the engine's own name for that run ("oracle") is not shown to anyone
    assert str(exc.value) == "bad file"
    assert lines.reference_failed == "bad file"
    assert eb._plain_reason("colprof oracle failed: ") == \
        "colprof ended with an error"
    assert eb._plain_reason("a86: oracle A2B sampling failed") == \
        "the result of the colprof run could not be read"
    assert eb._plain_reason("colprof did not finish within 30 minutes") == \
        "colprof did not finish within 30 minutes"
    # ...and every later line, from whichever thread, stops it again
    with pytest.raises(eb.ColprofReferenceFailed):
        lines("30% · Inverting the model…")
    assert shown == ["10% · Fitting the printer model…"]


def test_a_multi_ink_build_goes_on_and_says_so():
    """colprof cannot build these at all, so there is nothing to fall back
    to; the line is a clear warning instead of the engine's own words."""
    shown: list = []
    lines = eb.EngineLines(shown.append, multi_ink=True)
    lines("18% · Using the engine's own rendering (Argyll binaries not "
          "found).")
    assert lines.reference_failed == ""
    assert len(shown) == 1 and "[WARNING]" in shown[0]
    assert "Argyll binaries not found" in shown[0]
    assert "engine's own rendering" not in shown[0]


def test_no_user_text_of_the_adapter_names_research_or_a_switch():
    import ast
    tree = ast.parse((ROOT / "workflow/engine_builder.py").read_text("utf-8"))
    found = [n.args[0].value for n in ast.walk(tree)
             if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "tr"
             and n.args and isinstance(n.args[0], ast.Constant)]
    assert len(found) >= 8
    for text in found:
        assert not re.search(r"research|\bagent \d|\ba\d{2,3}-|token|"
                             r"candidate", text, re.I), text
        assert "—" not in text or "Multi-ink measurement" in text, text


@pytest.mark.slow
def test_a_real_build_without_colprof_stops_and_leaves_no_profile(
        tmp_path, qtbot):
    """End to end on the real engine: the ArgyllCMS folder points at
    nothing, so colprof cannot give the reference. The build ends with
    `reference_failed` set, nothing is written, and no error text is shown
    (the caller builds with colprof instead)."""
    ti3 = _rgb_ti3(tmp_path / "s.ti3")
    lines, done = [], []
    b = eb.EngineProfileBuilder(_Fake(argyll_bin_path=str(tmp_path / "no")))
    from core.resource_path import resource_path
    b.build(ProfileParams(ti3_path=ti3, quality="l", gamut_src=str(
        resource_path("assets/profiles/ClayRGB1998.icm"))),
        on_line=lines.append, on_finish=done.append)
    qtbot.waitUntil(lambda: bool(done) and not b.is_running, timeout=240_000)
    assert done == [1]
    assert b.reference_failed, lines
    assert b.primary_failure() is None
    assert not ti3.with_suffix(".icc").exists()
    assert not any("[ERROR]" in ln or "own rendering" in ln for ln in lines)


def _thread_on(monkeypatch, tmp_path, fake_build):
    """An engine thread over an RGB measurement whose profile and v4 twin
    already exist (the archive into ``old/`` failed, say), with
    ``build_profile`` replaced by *fake_build*. Run in this thread."""
    import workflow.profile_engine as pe
    from workflow.profile_engine.builder import BuildSettings
    ti3 = _rgb_ti3(tmp_path / "s.ti3")
    icc = ti3.with_suffix(".icc")
    twin = icc.with_name(icc.stem + "-v4.icc")
    icc.write_bytes(b"the previous profile " * 50)
    twin.write_bytes(b"the previous twin " * 50)
    monkeypatch.setattr(pe, "build_profile", fake_build)
    t = eb._EngineThread(ti3, icc, BuildSettings())
    return t, icc, twin


def test_a_reference_failure_never_removes_a_profile_it_did_not_write(
        tmp_path, monkeypatch):
    """Review 2026-11-11 (F1): the stop for a missing colprof reference
    removed whatever stood at the output paths. When the previous profile
    was still there (its move into ``old/`` had failed), that was the
    previous profile, and with colprof broken the build that follows fails
    too: the run was left with no profile at all."""
    def fake(ti3, out, settings):
        settings.progress("Using the engine's own rendering (colprof oracle "
                          "failed: colprof: not found).")
        raise AssertionError("not reached")

    t, icc, twin = _thread_on(monkeypatch, tmp_path, fake)
    t.run()
    assert t.reference_failed
    assert icc.read_bytes().startswith(b"the previous profile")
    assert twin.read_bytes().startswith(b"the previous twin")


def test_a_reference_failure_after_writing_removes_what_it_wrote(
        tmp_path, monkeypatch):
    def fake(ti3, out, settings):
        Path(out).write_bytes(b"half a profile")
        settings.progress("Using the engine's own rendering (colprof oracle "
                          "failed: boom).")
        raise AssertionError("not reached")

    t, icc, twin = _thread_on(monkeypatch, tmp_path, fake)
    t.run()
    assert t.reference_failed
    assert not icc.exists()                       # it wrote this one
    assert twin.read_bytes().startswith(b"the previous twin")


def test_an_engine_error_after_writing_leaves_no_profile_of_its_own(
        tmp_path, monkeypatch):
    """Review 2026-11-11 (F2): an engine error AFTER the profile file was
    written left that file in the run. The tab then reported the build as
    failed and could not put the previous profile back from ``old/``,
    because a file already stood in its place."""
    def fake(ti3, out, settings):
        Path(out).write_bytes(b"a profile of a failed build " * 50)
        raise RuntimeError("the twin could not be written")

    t, icc, twin = _thread_on(monkeypatch, tmp_path, fake)
    errors: list = []
    t.done.connect(lambda code, err: errors.append((code, err)))
    t.run()
    assert errors == [(1, "the twin could not be written")]
    assert not icc.exists()
    assert twin.read_bytes().startswith(b"the previous twin")


def test_an_engine_error_before_writing_keeps_what_was_there(
        tmp_path, monkeypatch):
    def fake(ti3, out, settings):
        raise RuntimeError("the model could not be fitted")

    t, icc, twin = _thread_on(monkeypatch, tmp_path, fake)
    t.run()
    assert icc.read_bytes().startswith(b"the previous profile")
    assert twin.read_bytes().startswith(b"the previous twin")


# ---------------------------------------------------------------------------
# B2 in the tab: the build goes to colprof and says so
# ---------------------------------------------------------------------------

def _run_with_ti3(tab, tmp_path, name="Arch"):
    root = tmp_path / "out"          # never the worker's shared folder
    tab._settings.set("custom_output_path", str(root))
    proj = Project.create(root / name, name)
    run = proj.current_run()
    ti3 = _rgb_ti3(run.measurement_ti3)
    run.save_meta(run.load_meta())
    tab._settings.set("target_name", name)
    tab.set_ti3_path(ti3, propagate=False)
    return run, ti3


def _quiet_windows(monkeypatch, tab):
    shown: list = []
    from ui.tabs import tab_profile as tp

    class _Info:
        def __init__(self, title, body, *_a, **_k):
            shown.append((title, body))

        def exec(self):
            return 0

    monkeypatch.setattr(tp, "InfoDialog", _Info)
    monkeypatch.setattr(tab, "_show_build_result_dialog",
                        lambda *a, **k: shown.append(("result", str(a[0]))))
    return shown


def test_a_failed_reference_builds_with_colprof_and_tells_the_user(
        tmp_path, qtbot, monkeypatch):
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    run, ti3 = _run_with_ti3(tab, tmp_path)
    shown = _quiet_windows(monkeypatch, tab)
    params = ProfileParams(ti3_path=ti3)
    tab._active_params = params
    calls: list = []

    def colprof_build(p, on_line, on_finish):
        calls.append(p)
        ti3.with_suffix(".icc").write_bytes(b"colprof made this " * 100)
        on_finish(0)

    monkeypatch.setattr(tab._builder, "build", colprof_build)
    monkeypatch.setattr(tab._builder, "sanity_check", lambda *_a, **_k: [])
    tab._engine_builder.reference_failed = "colprof oracle failed: boom"
    tab._on_engine_done(1)
    assert calls == [params]
    log = tab._log.toPlainText()
    assert "[INFO] The new profile engine could not be used" in log
    assert "colprof oracle failed: boom" in log
    assert "Profile saved" in log
    title, body = shown[0]
    assert title == ("Built with ArgyllCMS colprof instead of the new "
                     "profile engine")
    assert "colprof oracle failed: boom" in body and "untouched" in body
    assert shown[1][0] == "result"
    assert len(shown) == 2                       # the window shows once
    rec = run.load_meta().profile_build
    assert rec["builder"] == "colprof"
    assert rec["instead_of_the_engine_because"] == \
        "colprof oracle failed: boom"
    assert not run.colprof_comparison_icc.exists()


def test_an_engine_error_puts_the_previous_profile_back(
        tmp_path, qtbot, monkeypatch):
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    run, ti3 = _run_with_ti3(tab, tmp_path)
    shown = _quiet_windows(monkeypatch, tab)
    icc = ti3.with_suffix(".icc")
    twin = icc.with_name(icc.stem + "-v4.icc")
    icc.write_bytes(b"old profile bytes " * 100)
    twin.write_bytes(b"old twin bytes " * 100)
    run.colprof_comparison_icc.write_bytes(b"old comparison " * 100)
    params = ProfileParams(ti3_path=ti3)
    tab._active_params = params
    tab._archive_the_profile_being_replaced(params)
    assert not icc.exists() and not twin.exists()
    assert not run.colprof_comparison_icc.exists()
    assert sorted(p.name for p in (run.dir / "old").rglob("*.icc")) == [
        "Arch-v4.icc", "Arch.icc", COLPROF_COMPARISON_NAME]
    tab._engine_builder._last_error = "the model could not be fitted"
    tab._engine_builder.reference_failed = ""
    tab._on_engine_done(1)
    assert icc.exists() and twin.exists()
    assert run.colprof_comparison_icc.exists()
    assert not list((run.dir / "old").rglob("*.icc"))
    assert "The previous profile was put back" in tab._log.toPlainText()
    assert shown and "could not be fitted" in shown[0][1]
    tab._restore_archived_build()                # once only
    assert icc.read_bytes().startswith(b"old profile bytes")


def test_with_the_switch_off_the_archive_is_what_it_always_was(
        tmp_path, qtbot):
    tab = _tab(tmp_path, profile_engine_beta=False)
    qtbot.addWidget(tab)
    run, ti3 = _run_with_ti3(tab, tmp_path)
    icc = ti3.with_suffix(".icc")
    twin = icc.with_name(icc.stem + "-v4.icc")
    icc.write_bytes(b"old profile bytes " * 100)
    twin.write_bytes(b"old twin bytes " * 100)
    run.colprof_comparison_icc.write_bytes(b"of the old profile " * 100)
    tab._archive_the_profile_being_replaced(ProfileParams(ti3_path=ti3))
    assert not icc.exists() and twin.exists()
    # a comparison left by an earlier engine build goes with its profile
    assert not run.colprof_comparison_icc.exists()
    assert sorted(p.name for p in (run.dir / "old").rglob("*.icc")) == [
        "Arch.icc", COLPROF_COMPARISON_NAME]
    tab._restore_archived_build()
    assert not icc.exists()
    assert "put back" not in tab._log.toPlainText()


# ---------------------------------------------------------------------------
# B3 / B4 in the tab: the record, and colprof's profile beside the engine's
# ---------------------------------------------------------------------------

def test_a_finished_engine_build_is_recorded_and_gets_its_comparison(
        tmp_path, qtbot, monkeypatch):
    from ui.tabs import tab_profile as tp
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    run, ti3 = _run_with_ti3(tab, tmp_path)
    shown = _quiet_windows(monkeypatch, tab)
    icc = ti3.with_suffix(".icc")
    icc.write_bytes(b"the engine made this " * 100)
    params = ProfileParams(ti3_path=ti3, description="Arch on Baryta",
                           icc_version="both", spectral_physics=True)
    tab._active_params = params
    tab._engine_builder.reference_failed = ""
    tab._engine_builder.last_record = {
        "builder": "engine", "engine_mode": "accurate",
        "black_depth": "deepest", "settings": "quality='m'",
        "switches_on": ["a25-oog", "b2a33s"],
        "switches_reported": [{"switch": "a58-purecolprof", "line": "x"}],
        "dark_end": None}
    monkeypatch.setattr(tab._runner, "tool_is_installed", lambda _t: True)
    seen: list = []

    def fake_build(self, p, on_line, on_finish):
        seen.append(p)
        assert p.ti3_path != ti3 and p.ti3_path.name == ti3.name
        assert p.ti3_path.read_bytes() == ti3.read_bytes()
        on_line(" 50%")
        Path(str(p.ti3_path.with_suffix("")) + ".icc").write_bytes(
            b"colprof made this " * 100)
        on_finish(0)

    monkeypatch.setattr(tp.ProfileBuilder, "build", fake_build)
    tab._on_engine_done(0)

    cmp_icc = run.colprof_comparison_icc
    assert cmp_icc.name == COLPROF_COMPARISON_NAME
    assert cmp_icc.read_bytes().startswith(b"colprof made this")
    assert icc.read_bytes().startswith(b"the engine made this")
    c = seen[0]
    assert c.description == "Arch on Baryta (colprof)"
    assert (c.icc_version, c.spectral_physics) == ("2", False)
    assert not c.ti3_path.parent.exists()        # the work folder is gone
    log = tab._log.toPlainText()
    assert "saved beside the new one for comparison" in log
    assert str(cmp_icc) in log and "Profile saved" in log
    assert " 50%" not in log                     # colprof's lines stay out
    assert shown == [("result", str(icc))]
    rec = run.load_meta().profile_build
    assert rec["builder"] == "engine" and rec["black_depth"] == "deepest"
    assert rec["switches_on"] == ["a25-oog", "b2a33s"]
    assert rec["switches_reported"][0]["switch"] == "a58-purecolprof"
    assert rec["profile"] == icc.name and rec["at"]
    assert tab._icc_path == icc                  # the run's profile, not it


def test_a_failed_comparison_never_fails_the_build(
        tmp_path, qtbot, monkeypatch):
    from ui.tabs import tab_profile as tp
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    run, ti3 = _run_with_ti3(tab, tmp_path)
    shown = _quiet_windows(monkeypatch, tab)
    icc = ti3.with_suffix(".icc")
    icc.write_bytes(b"the engine made this " * 100)
    tab._active_params = ProfileParams(ti3_path=ti3)
    monkeypatch.setattr(tab._runner, "tool_is_installed", lambda _t: True)
    monkeypatch.setattr(tp.ProfileBuilder, "build",
                        lambda self, p, on_line, on_finish: on_finish(1))
    tab._on_engine_done(0)
    assert not run.colprof_comparison_icc.exists()
    log = tab._log.toPlainText()
    assert "comparison profile from ArgyllCMS colprof could not be built" \
        in log
    assert "Profile saved" in log and shown == [("result", str(icc))]


def test_a_multi_ink_build_has_no_comparison(tmp_path, qtbot, monkeypatch):
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    ti3 = _multi_ink_ti3(tmp_path / "og.ti3")
    assert tab._start_colprof_comparison(ProfileParams(ti3_path=ti3)) is False
    assert not (tmp_path / COLPROF_COMPARISON_NAME).exists()


def test_a_colprof_build_with_the_switch_off_writes_no_record(
        tmp_path, qtbot):
    tab = _tab(tmp_path, profile_engine_beta=False)
    qtbot.addWidget(tab)
    run, ti3 = _run_with_ti3(tab, tmp_path)
    before = run.meta_path.read_bytes()
    tab._note_a_colprof_build(ti3.with_suffix(".icc"))
    assert run.meta_path.read_bytes() == before
    # ...but an engine record is not left describing a colprof profile
    run.record_profile_build({"builder": "engine"})
    tab._note_a_colprof_build(ti3.with_suffix(".icc"))
    assert run.load_meta().profile_build["builder"] == "colprof"


def test_a_loose_measurement_gets_no_meta_file(tmp_path, qtbot):
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    ti3 = _rgb_ti3(tmp_path / "loose" / "x.ti3") if (
        tmp_path / "loose").mkdir() is None else None
    tab._record_profile_build(ti3.with_suffix(".icc"), {"builder": "engine"})
    assert not (ti3.parent / "meta.json").exists()


# ---------------------------------------------------------------------------
# B4 in the file layer: the comparison never answers for the run
# ---------------------------------------------------------------------------

def test_the_comparison_profile_is_role_named_and_is_not_the_runs_profile(
        tmp_path):
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    cmp_icc = run.colprof_comparison_icc
    assert cmp_icc == run.dir / "colprof-comparison.icc"
    cmp_icc.write_bytes(b"x" * 2000)
    assert run.profile_icc != cmp_icc and not run.profile_icc.exists()
    assert run.built_profile_icc() != cmp_icc
    assert not run.built_profile_icc().exists()


def test_a_run_holding_only_the_comparison_has_no_profile(tmp_path):
    from core import file_manager as fm
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.colprof_comparison_icc.write_bytes(b"x" * 2000)
    src = Path(fm.__file__).read_text(encoding="utf-8")
    assert re.search(r'profile=_any\("\*\.icc", "\*\.icm", skip=\('
                     r'"preconditioning\.icc",\s*COLPROF_COMPARISON_NAME\)\)',
                     src)
    peek = fm.peek_project(proj.root)
    assert peek.runs and all(r.profile is False for r in peek.runs), peek
    (run.dir / "P.icc").write_bytes(b"y" * 2000)
    assert run.profile_icc.exists()


def test_the_comparison_travels_with_the_profile_it_belongs_to(tmp_path):
    groups = dict(Project.DUPLICATE_GROUPS)
    assert COLPROF_COMPARISON_NAME in groups["profile"]
    src = (ROOT / "core/file_manager.py").read_text(encoding="utf-8")
    assert src.count("self.colprof_comparison_icc]") >= 1      # archived
    assert "COLPROF_COMPARISON_NAME,     # colprof's profile beside" in src
    from ui.tabs.tab_profile import _ROLE_NAMED_PROFILES
    # installing it would not give it the project's name by accident
    assert COLPROF_COMPARISON_NAME not in _ROLE_NAMED_PROFILES


def test_the_build_record_survives_meta_json(tmp_path):
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    assert run.load_meta().profile_build == {}
    run.record_profile_build({"builder": "engine", "switches_on": ["x"]})
    assert Run.for_dir(run.dir).load_meta().profile_build == {
        "builder": "engine", "switches_on": ["x"]}
    assert RunMeta.from_dict({"run_id": "run1"}).profile_build == {}


# ---------------------------------------------------------------------------
# A. the pieces taken from the earlier UI work
# ---------------------------------------------------------------------------

def test_restore_defaults_resets_the_engine_and_black_generation_rows(
        tmp_path, qtbot):
    """B-18: a run with nothing stored opens on the saved defaults for
    EVERY Manual control (per_target_settings.md section 4, S4 to S7)."""
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    tab._m_spectral_cb.setChecked(True)
    tab._m_iccver_combo.setCurrentIndex(tab._m_iccver_combo.findData("both"))
    tab._m_noise_cb.setChecked(True)
    tab._m_render_combo.setCurrentIndex(
        tab._m_render_combo.findData("bijective"))
    tab._m_kgen_combo.setCurrentIndex(tab._m_kgen_combo.findData("p"))
    tab._m_kgen_spins["stpo"].setValue(0.4)
    tab._restore_defaults()
    assert tab._m_spectral_cb.isChecked() is False
    assert tab._m_iccver_combo.currentData() == "2"
    assert tab._m_noise_cb.isChecked() is False
    assert tab._m_render_combo.currentData() == "argyll"
    assert (tab._m_kgen_combo.currentData() or "") == ""
    assert tab._m_kgen_spins["stpo"].value() == pytest.approx(0.1)


def test_the_engine_rows_follow_the_switch_alone(tmp_path, qtbot):
    tab = _tab(tmp_path, profile_engine_beta=True, gammap_mode="fast")
    qtbot.addWidget(tab)
    tab._refresh_engine_rows()
    assert not tab._m_engine_rows_widget.isHidden()
    tab._settings.set("profile_engine_beta", False)
    tab._refresh_engine_rows()
    assert tab._m_engine_rows_widget.isHidden()


def test_the_quit_question_is_asked_only_while_the_engine_builds(
        monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    from ui.main_window import MainWindow

    class Fake(eb.EngineProfileBuilder):
        def __init__(self, running):
            self._running = running

        @property
        def is_running(self):
            return self._running

    asked: list = []
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda self: asked.append(
                            (self.text(), self.informativeText(),
                             [b.text() for b in self.buttons()],
                             self.defaultButton().text())) or 0)
    eb.EngineProfileBuilder._RUNNING.clear()
    ask = MainWindow._ask_before_quitting_on_a_build
    assert ask(None) is True and not asked
    b = Fake(True)
    eb.EngineProfileBuilder._RUNNING.add(b)
    try:
        # nothing clicked reads as "quit anyway" is NOT assumed: the default
        # and Esc are "Keep building"; here no button was clicked at all
        ask(None)
        title, body, buttons, default = asked[0]
        assert title == "A profile is still being built"
        assert "not saved" in body and "old" in body
        assert sorted(buttons) == ["Keep building", "Quit anyway"]
        assert default == "Keep building"
        b._running = False
        assert ask(None) is True and len(asked) == 1
    finally:
        eb.EngineProfileBuilder._RUNNING.discard(b)


def test_close_asks_about_the_build_before_closing_down():
    import inspect

    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow.closeEvent)
    assert src.index("_ask_before_quitting_on_a_measurement()") < \
        src.index("_ask_before_quitting_on_a_build()") < \
        src.index("_close_down(event)")
