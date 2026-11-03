"""FWA compensation (-f) is never offered for, nor passed with, an FD-9
measurement (fix_fwa, 2026-11-03).

ArgyllCMS models optical brighteners from the lamp of the instrument that took
the readings, found by TARGET_INSTRUMENT. It does not know the FD-9, so
colprof, profcheck and spec2cie all stop at once:

    colprof: Error - Unrecognised target instrument 'Konica Minolta FD-9'

Measured with ArgyllCMS 3.5.0: the illuminant (-i) and observer (-o) work on
the same file, and the same file named "GretagMacbeth i1 Pro" builds with -f.
So only FWA is gated, only for an FD-9 name (either spelling), Beta on or off,
and every other measurement is exactly as before.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from core.argyll_runner import ArgyllRunner
from core.settings import AppSettings

ROOT = Path(__file__).resolve().parents[1]
#: A real 616-patch spectral measurement (36 bands, 380-730 nm) in the repo.
BASE = (ROOT / "tests/data/g_basti_et8550_run1_verify/"
        "ET8550_EpsPremSG_AdobeRGB_CM_Okt26-verify.ti3")
ARGYLL = Path("/Applications/Argyll/bin")

FD9_NAMES = ("Konica Minolta FD-9", "FD-9")
OTHER_NAMES = ("GretagMacbeth i1 Pro", "X-Rite i1 Pro 3",
               "X-Rite ColorMunki", "CHNSpec CR30")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _ti3(tmp_path: Path, instrument: str, stem: str = "m") -> Path:
    """The repo's spectral measurement, re-labelled as *instrument*."""
    lines = []
    for line in BASE.read_text(encoding="utf-8").splitlines():
        if line.startswith("TARGET_INSTRUMENT "):
            line = f'TARGET_INSTRUMENT "{instrument}"'
        if "CHROMIQ_VERIFICATION" in line:
            continue
        lines.append(line)
    folder = tmp_path / stem
    folder.mkdir(exist_ok=True)
    out = folder / f"{stem}.ti3"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def _settings(tmp_path, **prefs) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    for k, v in prefs.items():
        s.set(k, v)
    return s


def _profile_tab(tmp_path, monkeypatch, **prefs):
    from ui.tabs.tab_profile import TabProfile
    s = _settings(tmp_path, **prefs)
    runner = ArgyllRunner(s)
    calls: list = []
    monkeypatch.setattr(runner, "run",
                        lambda tool, args, cwd, **k: calls.append(
                            (tool, list(args))))
    return TabProfile(runner, s), calls


def _check_tab(tmp_path, monkeypatch, **prefs):
    from ui.tabs.tab_check_refine import TabCheckRefine
    s = _settings(tmp_path, **prefs)
    runner = ArgyllRunner(s)
    calls: list = []
    monkeypatch.setattr(runner, "run",
                        lambda tool, args, cwd, **k: calls.append(
                            (tool, list(args))))
    return TabCheckRefine(runner, s), calls


def _fwa_in(args) -> list:
    return [a for a in args if a.startswith("-f")]


# ---------------------------------------------------------------------------
# The name check
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", FD9_NAMES + ("fd-9", '"FD-9"'))
def test_an_fd9_name_shuts_the_fwa_gate(name):
    from workflow.fwa_gate import fwa_refusal
    assert fwa_refusal(name).kind == "fd9"


@pytest.mark.parametrize("name", OTHER_NAMES + (None, "", "FD-7"))
def test_no_other_name_shuts_it(name):
    from workflow.fwa_gate import fwa_refusal
    assert fwa_refusal(name) is None


def test_the_spectral_gate_is_untouched_by_the_fd9():
    """The FD-9 carries spectra: the old spectral gate says nothing new."""
    from ui.ti2_loader import spectral_options_unavailable
    for name in FD9_NAMES:
        assert spectral_options_unavailable(name, True) is False


def test_the_gate_does_not_ask_the_beta(tmp_path):
    """ArgyllCMS refuses -f on an FD-9 file whatever the switch says."""
    from workflow.fwa_gate import fwa_refusal_for_file
    from workflow.fd9 import support
    ti3 = _ti3(tmp_path, FD9_NAMES[0])
    try:
        for on in (True, False):
            support.set_enabled_for_this_process(on)
            assert fwa_refusal_for_file(ti3).kind == "fd9"
    finally:
        support.set_enabled_for_this_process(None)


# ---------------------------------------------------------------------------
# Build Profile
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", FD9_NAMES)
def test_build_profile_greys_fwa_for_an_fd9_measurement(
        qapp, tmp_path, monkeypatch, name):
    from workflow.fwa_gate import FwaRefusal
    tab, _ = _profile_tab(tmp_path, monkeypatch)
    tab._m_fwa_check.setChecked(True)
    tab.set_ti3_path(_ti3(tmp_path, name))
    reason = FwaRefusal("fd9").reason
    for w in (tab._fwa_check, tab._fwa_illum_combo,
              tab._m_fwa_check, tab._m_fwa_illum_combo):
        assert not w.isEnabled()
        assert w.toolTip() == reason
    # A preset or saved setting that ticks the box cannot wake the combo.
    tab._fwa_check.setChecked(True)
    assert not tab._fwa_illum_combo.isEnabled()
    # Illuminant and observer work with FD-9 data: left alone.
    assert tab._m_illum_combo.isEnabled() and tab._m_obs_combo.isEnabled()
    tab.deleteLater()


@pytest.mark.parametrize("name", OTHER_NAMES[:3])
def test_build_profile_is_unchanged_for_other_spectral_measurements(
        qapp, tmp_path, monkeypatch, name):
    tab, _ = _profile_tab(tmp_path, monkeypatch)
    plain = {id(w): w.toolTip() for w in (tab._fwa_check, tab._m_fwa_check,
                                         tab._fwa_illum_combo,
                                         tab._m_fwa_illum_combo)}
    tab.set_ti3_path(_ti3(tmp_path, name))
    for box, combo in ((tab._fwa_check, tab._fwa_illum_combo),
                       (tab._m_fwa_check, tab._m_fwa_illum_combo)):
        assert box.isEnabled() and not combo.isEnabled()
        box.setChecked(True)
        assert combo.isEnabled()
        assert box.toolTip() == plain[id(box)]
        assert combo.toolTip() == plain[id(combo)]
    tab._switch_mode("manual")
    assert tab._collect_params().fwa_enabled is True
    tab.deleteLater()


def test_loading_another_measurement_after_an_fd9_ungreys_it(
        qapp, tmp_path, monkeypatch):
    tab, _ = _profile_tab(tmp_path, monkeypatch)
    plain = tab._m_fwa_check.toolTip()
    tab.set_ti3_path(_ti3(tmp_path, FD9_NAMES[0], "a"))
    assert not tab._m_fwa_check.isEnabled()
    tab.set_ti3_path(_ti3(tmp_path, OTHER_NAMES[0], "b"))
    assert tab._m_fwa_check.isEnabled()
    assert tab._m_fwa_check.toolTip() == plain
    tab.deleteLater()


@pytest.mark.parametrize("mode", ["guided", "manual"])
def test_the_build_never_passes_f_for_an_fd9_measurement(
        qapp, tmp_path, monkeypatch, mode):
    """Ticked before the file was loaded (as a preset, a saved per-target
    setting or the Guided defaults would): the build runs without -f, says
    so in the log, and the command box shows what runs. (The tab has no
    extra-arguments field; the builder test below covers a typed -f.)"""
    tab, calls = _profile_tab(tmp_path, monkeypatch)
    tab._switch_mode(mode)
    tab._fwa_check.setChecked(True)
    tab._m_fwa_check.setChecked(True)
    tab.set_ti3_path(_ti3(tmp_path, FD9_NAMES[0]))
    params = tab._collect_params()
    assert params.fwa_enabled is False
    tab.refresh_argyll_commands(every=True)
    box = tab._guided_cmd_box if mode == "guided" else tab._manual_cmd_box
    assert " -f" not in box.text()
    for name in ("_confirm_build_from_incomplete",
                 "_confirm_building_outside_the_selected_run",
                 "_confirm_rebuild_over_verifications",
                 "_validate_gamut_source"):
        monkeypatch.setattr(tab, name, lambda *a, **k: True)
    monkeypatch.setattr(tab, "_refuse_when_the_profiler_is_not_installed",
                        lambda *a, **k: False)
    monkeypatch.setattr(tab, "_archive_the_profile_being_replaced",
                        lambda *a, **k: None)
    tab._on_build()
    assert [c[0] for c in calls] == ["colprof"]
    assert _fwa_in(calls[0][1]) == []
    assert "[NOTE] FWA compensation (-f) was left out" in tab._log.toPlainText()
    tab.deleteLater()


def test_the_builder_drops_f_whatever_hands_it_over(tmp_path):
    """The floor under every caller: ProfileBuilder itself."""
    from workflow.profile_builder import ProfileBuilder, ProfileParams
    for name in FD9_NAMES:
        ti3 = _ti3(tmp_path, name, "x" + str(len(name)))
        p = ProfileParams(ti3_path=ti3, fwa_enabled=True, fwa_illum="D50",
                          extra_args="-f -nc")
        args = ProfileBuilder(None)._build_args(p)
        assert _fwa_in(args) == [] and "-nc" in args
        # The caller's own object is left as it was.
        assert p.fwa_enabled is True and p.extra_args == "-f -nc"

    lines, ran = [], []

    class _Runner:
        def run(self, tool, args, cwd, **k):
            ran.append(list(args))

    ti3 = _ti3(tmp_path, FD9_NAMES[0], "built")
    ProfileBuilder(_Runner()).build(
        ProfileParams(ti3_path=ti3, fwa_enabled=True),
        on_line=lines.append, on_finish=lambda code: None)
    assert _fwa_in(ran[0]) == []
    assert any(line.startswith("[NOTE] FWA compensation") for line in lines)


def test_the_builder_keeps_f_for_every_other_measurement(tmp_path):
    from workflow.profile_builder import ProfileBuilder, ProfileParams
    for name in OTHER_NAMES:
        ti3 = _ti3(tmp_path, name, "o" + str(OTHER_NAMES.index(name)))
        p = ProfileParams(ti3_path=ti3, fwa_enabled=True, fwa_illum="D50",
                          extra_args="-f")
        assert _fwa_in(ProfileBuilder(None)._build_args(p)) == ["-fD50", "-f"]


# ---------------------------------------------------------------------------
# Check & Refine
# ---------------------------------------------------------------------------

def test_check_refine_greys_fwa_for_an_fd9_measurement(
        qapp, tmp_path, monkeypatch):
    from workflow.fwa_gate import FwaRefusal
    tab, calls = _check_tab(tmp_path, monkeypatch)
    tab._fwa_cb.setChecked(True)
    tab._m_fwa_cb.setChecked(True)
    icc = tmp_path / "p.icc"
    icc.write_bytes(b"\0" * 128)
    tab.set_paths(_ti3(tmp_path, FD9_NAMES[1]), icc, propagate=False)
    for w in (tab._fwa_cb, tab._fwa_combo, tab._m_fwa_cb, tab._m_fwa_combo):
        assert not w.isEnabled()
        assert w.toolTip() == FwaRefusal("fd9").reason
    assert tab._collect_params().fwa_enabled is False
    tab.deleteLater()


def test_check_refine_is_unchanged_for_an_i1pro_measurement(
        qapp, tmp_path, monkeypatch):
    tab, _ = _check_tab(tmp_path, monkeypatch)
    icc = tmp_path / "p.icc"
    icc.write_bytes(b"\0" * 128)
    tab.set_paths(_ti3(tmp_path, OTHER_NAMES[0]), icc, propagate=False)
    tab._fwa_cb.setChecked(True)
    tab._m_fwa_cb.setChecked(True)
    for box, combo in ((tab._fwa_cb, tab._fwa_combo),
                       (tab._m_fwa_cb, tab._m_fwa_combo)):
        assert box.isEnabled() and combo.isEnabled()
    assert tab._collect_params().fwa_enabled is True
    tab.deleteLater()


def test_profcheck_runner_drops_f_for_an_fd9_measurement(tmp_path):
    from workflow.profcheck_runner import ProfcheckParams, ProfcheckRunner
    ran, lines = [], []

    class _Runner:
        _settings = {}

        def run(self, tool, args, cwd=None, **k):
            ran.append(list(args))

    ti3 = _ti3(tmp_path, FD9_NAMES[0])
    ProfcheckRunner(_Runner()).run(
        ProfcheckParams(ti3_path=ti3, icc_path=tmp_path / "p.icc",
                        fwa_enabled=True),
        on_line=lines.append, on_finish=lambda code: None)
    assert ran and _fwa_in(ran[0]) == []
    assert any(line.startswith("[NOTE] FWA compensation") for line in lines)


# ---------------------------------------------------------------------------
# ArgyllCMS itself: the premise, and that the rest still builds
# ---------------------------------------------------------------------------

_needs_colprof = pytest.mark.skipif(not (ARGYLL / "colprof").is_file(),
                                    reason="ArgyllCMS colprof not installed")


def _colprof(ti3: Path, *opts) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            [str(ARGYLL / "colprof"), "-ql", *opts, "-O",
             str(ti3.with_suffix(".icc")), str(ti3.with_suffix(""))],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=600, cwd=ti3.parent)
    except subprocess.TimeoutExpired:
        pytest.fail("colprof did not finish within 600 s")


@_needs_colprof
def test_colprof_refuses_f_on_an_fd9_measurement(tmp_path):
    """Why the gate exists. If ArgyllCMS ever learns the FD-9 this fails, and
    the gate can be reconsidered."""
    ti3 = _ti3(tmp_path, FD9_NAMES[0])
    res = _colprof(ti3, "-f")
    assert res.returncode != 0
    assert "Unrecognised target instrument" in res.stdout + res.stderr


@_needs_colprof
def test_colprof_builds_an_fd9_measurement_with_the_remaining_options(
        tmp_path):
    from workflow.profile_builder import ProfileBuilder, ProfileParams
    ti3 = _ti3(tmp_path, FD9_NAMES[0])
    p = ProfileParams(ti3_path=ti3, quality="l", fwa_enabled=True,
                      illuminant="D65", observer="1964_10")
    args = ProfileBuilder(None)._build_args(p)
    assert _fwa_in(args) == [] and "-i" in args and "-o" in args
    try:
        res = subprocess.run([str(ARGYLL / "colprof"), *args,
                              str(ti3.with_suffix(""))],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=600,
                             cwd=ti3.parent)
    except subprocess.TimeoutExpired:
        pytest.fail("colprof did not finish within 600 s")
    assert res.returncode == 0, res.stdout[-2000:] + res.stderr[-2000:]
    assert ti3.with_suffix(".icc").is_file()
