"""THE FWA GATE (4.3.23, `workflow.fwa_gate`): FWA compensation (-f) is greyed,
with the reason, and never passed for a measurement ArgyllCMS cannot apply it
to, and nothing changes for one it can.

Before 4.3.23 the only gate for these files was `spectral_options_unavailable`
feeding a `_gated_options` list that has been empty in both tabs since 3.7.22,
so a measurement without spectra, a ColorMunki or a CR30 file was offered
FWA and only failed after colprof ran, with an error window.

Which names ArgyllCMS applies -f to was MEASURED, not guessed: every name in
ArgyllCMS 3.5.0's own instrument table was given to `spec2cie -f D50` on one
real spectral .ti3 (`test_the_list_is_exactly_what_argyll_accepts`).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from core.argyll_runner import ArgyllRunner
from core.settings import AppSettings
from workflow.fwa_gate import (ARGYLL_FWA_INSTRUMENTS, FwaRefusal,
                               fwa_refusal, fwa_refusal_for_file,
                               without_refused_fwa)

ROOT = Path(__file__).resolve().parents[1]
#: A real 616-patch spectral measurement (36 bands, 380-730 nm) in the repo.
BASE = (ROOT / "tests/data/g_basti_et8550_run1_verify/"
        "ET8550_EpsPremSG_AdobeRGB_CM_Okt26-verify.ti3")
ARGYLL = Path("/Applications/Argyll/bin")

#: Every instrument name string in ArgyllCMS 3.5.0's spec2cie (its inst_name
#: table and the alias table after it), as `strings spec2cie` lists them.
ARGYLL_TABLE = (
    "X-Rite DTP20", "X-Rite DTP22", "X-Rite DTP41", "X-Rite DTP51",
    "X-Rite DTP92", "X-Rite DTP94", "GretagMacbeth Spectrolino",
    "GretagMacbeth SpectroScan", "GretagMacbeth SpectroScanT",
    "GretagMacbeth i1 Display 1", "GretagMacbeth i1 Display 2",
    "X-Rite i1 DisplayPro, ColorMunki Display", "GretagMacbeth i1 Monitor",
    "GretagMacbeth i1 Pro", "X-Rite i1 Pro 2", "X-Rite i1 Pro 3",
    "X-Rite ColorMunki", "ColorVision Spyder1", "ColorVision Spyder2",
    "Datacolor Spyder3", "Datacolor Spyder4", "Datacolor Spyder5",
    "Datacolor SpyderX", "Datacolor SpyderX2", "Datacolor Spyder 2024",
    "GretagMacbeth Huey", "ColorMunki Smile", "JETI specbos 1201",
    "JETI specbos 2501", "JETI specbos", "JETI spectraval", "Klein K-10",
    "Image Engineering EX1", "SwatchMate Cube", "Hughski ColorHug",
    "Hughski ColorHug2", "Unknown Instrument",
    "Xrite DTP20", "Xrite DTP22", "Xrite DTP41", "Xrite DTP51",
    "Xrite DTP92", "Xrite DTP94", "GretagMacbeth i1 Display",
    "Xrite i1 Display", "X-Rite i1 Display", "Xrite i1 DisplayPro",
    "X-Rite i1 DisplayPro", "ColorMunki Display",
    "Xrite i1 DisplayPro, ColorMunki Display", "Xrite i1 Pro",
    "X-Rite i1 Pro", "Xrite i1 Pro 2", "Xrite i1 Pro 3", "XRite ColorMunki",
    "GretagMacbeth Spyder 2024",
)

#: Names ChromIQ writes or imports that ArgyllCMS refuses -f for, with the
#: kind of refusal the gate gives.
REFUSED = (
    ("X-Rite ColorMunki", "colormunki"),
    ("ColorMunki Smile", "colormunki"),
    ("CR30", "instrument"),
    ("CHNSpec CR30", "instrument"),
    ("i1iSis", "instrument"),
    ("X-Rite i1iSis", "instrument"),
    ("i1iSis 2 XL", "instrument"),
    ("i1Pro 3", "reimport"),
    ("i1Pro 3 Plus", "reimport"),
    ("i1Pro", "reimport"),
    ("i1Profiler (unspecified)", "no_name"),
    ("X-Rite i1 Studio", "instrument"),
    ("Konica Minolta FD-9", "fd9"),
    ("FD-9", "fd9"),
    ("X-Rite i1 Pro 3+", "instrument"),
    ("gretagmacbeth i1 pro", "instrument"),
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _ti3(tmp_path: Path, instrument: "str | None", stem: str = "m", *,
         spectra: bool = True, condition: "str | None" = None) -> Path:
    """The repo's spectral measurement, re-labelled as *instrument* (None:
    no TARGET_INSTRUMENT at all), optionally without its spectra or with a
    MEASUREMENT_CONDITION."""
    text = BASE.read_text(encoding="utf-8")
    text = "\n".join(ln for ln in text.splitlines()
                     if "CHROMIQ_VERIFICATION" not in ln) + "\n"
    if instrument is None:
        text = re.sub(r'^KEYWORD "TARGET_INSTRUMENT"\n', "", text, flags=re.M)
        text = re.sub(r'^TARGET_INSTRUMENT .*\n', "", text, flags=re.M)
    else:
        text = re.sub(r'^TARGET_INSTRUMENT .*$',
                      f'TARGET_INSTRUMENT "{instrument}"', text, flags=re.M)
    if condition:
        text = text.replace(
            "BEGIN_DATA_FORMAT",
            f'KEYWORD "MEASUREMENT_CONDITION"\nMEASUREMENT_CONDITION '
            f'"{condition}"\nBEGIN_DATA_FORMAT', 1)
    if not spectra:
        lines = text.splitlines()
        out, keep, in_fmt, in_data = [], None, False, False
        for ln in lines:
            if ln.startswith(("SPECTRAL_", 'KEYWORD "SPECTRAL_')):
                continue
            if ln == "BEGIN_DATA_FORMAT":
                in_fmt = True
            elif ln == "END_DATA_FORMAT":
                in_fmt = False
            elif ln == "BEGIN_DATA":
                in_data = True
            elif ln == "END_DATA":
                in_data = False
            elif in_fmt:
                toks = ln.split()
                keep = [i for i, t in enumerate(toks)
                        if not t.startswith("SPEC_")]
                ln = " ".join(toks[i] for i in keep)
            elif in_data and ln.strip():
                toks = ln.split()
                ln = " ".join(toks[i] for i in keep)
            out.append(ln)
        n = len(out[out.index("BEGIN_DATA_FORMAT") + 1].split())
        text = re.sub(r"^NUMBER_OF_FIELDS \d+", f"NUMBER_OF_FIELDS {n}",
                      "\n".join(out) + "\n", flags=re.M)
    folder = tmp_path / stem
    folder.mkdir(exist_ok=True)
    out_path = folder / f"{stem}.ti3"
    out_path.write_text(text, encoding="utf-8")
    return out_path


def _settings(tmp_path) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    return s


def _profile_tab(tmp_path, monkeypatch):
    from ui.tabs.tab_profile import TabProfile
    s = _settings(tmp_path)
    runner = ArgyllRunner(s)
    calls: list = []
    monkeypatch.setattr(runner, "run",
                        lambda tool, args, cwd, **k: calls.append(
                            (tool, list(args))))
    return TabProfile(runner, s), calls


def _check_tab(tmp_path, monkeypatch):
    from ui.tabs.tab_check_refine import TabCheckRefine
    s = _settings(tmp_path)
    runner = ArgyllRunner(s)
    calls: list = []
    monkeypatch.setattr(runner, "run",
                        lambda tool, args, cwd, **k: calls.append(
                            (tool, list(args))))
    return TabCheckRefine(runner, s), calls


def _fwa_in(args) -> list:
    return [a for a in args if a.startswith("-f")]


# ---------------------------------------------------------------------------
# The answer
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", sorted(ARGYLL_FWA_INSTRUMENTS))
def test_every_name_argyll_accepts_is_let_through(tmp_path, name):
    assert fwa_refusal(name) is None
    assert fwa_refusal(name, condition="M0") is None
    assert fwa_refusal_for_file(_ti3(tmp_path, name)) is None


@pytest.mark.parametrize("name, kind", REFUSED)
def test_every_name_argyll_refuses_is_refused_with_its_reason(
        tmp_path, name, kind):
    refusal = fwa_refusal_for_file(_ti3(tmp_path, name))
    assert refusal is not None and refusal.kind == kind
    assert refusal.reason and refusal.log_line.startswith("[NOTE] ")
    if kind in ("colormunki", "reimport", "instrument"):
        assert name in refusal.log_line


def test_no_spectra_is_refused_whatever_the_instrument(tmp_path):
    for i, name in enumerate(("GretagMacbeth i1 Pro", "CR30")):
        refusal = fwa_refusal_for_file(
            _ti3(tmp_path, name, f"n{i}", spectra=False))
        assert refusal.kind == "no_spectra"
        assert "no spectral readings" in refusal.reason


def test_no_instrument_name_is_refused(tmp_path):
    refusal = fwa_refusal_for_file(_ti3(tmp_path, None))
    assert refusal.kind == "no_name"
    assert fwa_refusal("").kind == "no_name"


@pytest.mark.parametrize("cond", ["M1", "M2"])
def test_m1_and_m2_are_refused_for_an_instrument_argyll_knows(tmp_path, cond):
    refusal = fwa_refusal_for_file(
        _ti3(tmp_path, "X-Rite i1 Pro 3", condition=cond))
    assert refusal.kind == "condition" and refusal.condition == cond
    assert cond in refusal.reason and cond in refusal.log_line


def test_the_order_names_what_helps_most(tmp_path):
    """FD-9 before no spectra before the instrument before the condition:
    an i1iSis M1 import is refused for its instrument (M0 would not help)."""
    assert fwa_refusal("FD-9", has_spectral=False).kind == "fd9"
    assert fwa_refusal("i1iSis", has_spectral=False).kind == "no_spectra"
    assert fwa_refusal("i1iSis", condition="M1").kind == "instrument"
    assert fwa_refusal("X-Rite i1 Pro 3", condition="M1").kind == "condition"


def test_nothing_loaded_is_nothing_refused(tmp_path):
    assert fwa_refusal_for_file(None) is None
    assert fwa_refusal_for_file(tmp_path / "missing.ti3") is None


def test_the_import_fallback_name_is_the_one_the_import_writes():
    from workflow import fwa_gate, reference_convert
    assert (fwa_gate._IMPORT_NAMES_NO_INSTRUMENT
            == reference_convert._IMPORTED_INSTRUMENT_FALLBACK)


def test_reimport_is_offered_only_where_the_import_now_names_it_for_argyll():
    from workflow.reference_convert import argyll_instrument_name
    for name, kind in REFUSED:
        if kind == "reimport":
            assert argyll_instrument_name(name) in ARGYLL_FWA_INSTRUMENTS


@pytest.mark.parametrize("kind", ["fd9", "no_spectra", "no_name",
                                  "colormunki", "reimport", "instrument",
                                  "condition"])
def test_every_reason_is_plain_text_without_an_em_dash(kind):
    r = FwaRefusal(kind, "Some Instrument", "M1")
    for text in (r.reason, r.log_line):
        assert text and "—" not in text and "{" not in text


# ---------------------------------------------------------------------------
# ArgyllCMS itself: the list is measured, and what passes builds with -f
# ---------------------------------------------------------------------------

_needs_argyll = pytest.mark.skipif(
    not (ARGYLL / "spec2cie").is_file() or not (ARGYLL / "colprof").is_file(),
    reason="ArgyllCMS not installed")


def _run(args, cwd) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(args, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=600, cwd=cwd)
    except subprocess.TimeoutExpired:
        pytest.fail(f"{Path(args[0]).name} did not finish within 600 s")


@_needs_argyll
def test_the_list_is_exactly_what_argyll_accepts(tmp_path):
    """If an ArgyllCMS update learns or forgets an instrument, this fails and
    `ARGYLL_FWA_INSTRUMENTS` is measured again."""
    accepted, refused = set(), {}
    for i, name in enumerate(ARGYLL_TABLE):
        ti3 = _ti3(tmp_path, name, f"a{i}")
        res = _run([str(ARGYLL / "spec2cie"), "-f", "D50", ti3.name,
                    "out.ti3"], ti3.parent)
        if res.returncode == 0:
            accepted.add(name)
        else:
            refused[name] = (res.stdout + res.stderr).strip()[-120:]
    assert accepted == set(ARGYLL_FWA_INSTRUMENTS), refused
    for name in ARGYLL_TABLE:
        if name not in accepted:
            assert fwa_refusal(name) is not None, name


@_needs_argyll
@pytest.mark.parametrize("name, kind", [r for r in REFUSED
                                        if r[1] != "no_name"] + [
    (None, "no_name"), ("i1Profiler (unspecified)", "no_name")])
def test_argyll_really_refuses_every_refused_name(tmp_path, name, kind):
    ti3 = _ti3(tmp_path, name)
    res = _run([str(ARGYLL / "spec2cie"), "-f", "D50", ti3.name, "o.ti3"],
               ti3.parent)
    assert res.returncode != 0, name
    ok = _run([str(ARGYLL / "spec2cie"), ti3.name, "o0.ti3"], ti3.parent)
    assert ok.returncode == 0, "only -f is refused"


@_needs_argyll
def test_argyll_refuses_f_without_spectra(tmp_path):
    ti3 = _ti3(tmp_path, "GretagMacbeth i1 Pro", spectra=False)
    res = _run([str(ARGYLL / "colprof"), "-ql", "-f", "-O", "x.icc",
                ti3.stem], ti3.parent)
    assert res.returncode != 0
    ok = _run([str(ARGYLL / "colprof"), "-ql", "-O", "x.icc", ti3.stem],
              ti3.parent)
    assert ok.returncode == 0, ok.stdout[-1500:] + ok.stderr[-1500:]


@_needs_argyll
def test_a_measurement_fwa_works_for_still_builds_with_f(tmp_path):
    from workflow.profile_builder import ProfileBuilder, ProfileParams
    ti3 = _ti3(tmp_path, "GretagMacbeth i1 Pro")
    p = ProfileParams(ti3_path=ti3, quality="l", fwa_enabled=True,
                      fwa_illum="D50")
    args = ProfileBuilder(None)._build_args(p)
    assert _fwa_in(args) == ["-fD50"]
    res = _run([str(ARGYLL / "colprof"), *args, ti3.stem], ti3.parent)
    assert res.returncode == 0, res.stdout[-2000:] + res.stderr[-2000:]
    assert ti3.with_suffix(".icc").is_file()


# ---------------------------------------------------------------------------
# The floor: every builder
# ---------------------------------------------------------------------------

def test_the_floor_drops_f_and_a_typed_f_with_its_value(tmp_path):
    from workflow.profile_builder import ProfileBuilder, ProfileParams
    ti3 = _ti3(tmp_path, "X-Rite ColorMunki")
    p = ProfileParams(ti3_path=ti3, fwa_enabled=True, fwa_illum="D50",
                      extra_args="-f D65 -nc")
    args = ProfileBuilder(None)._build_args(p)
    assert _fwa_in(args) == [] and "-nc" in args and "D65" not in args
    assert p.fwa_enabled is True, "the caller's object is left as it was"
    lines, ran = [], []

    class _Runner:
        def run(self, tool, args, cwd, **k):
            ran.append(list(args))

    ProfileBuilder(_Runner()).build(p, on_line=lines.append,
                                    on_finish=lambda code: None)
    assert ran and _fwa_in(ran[0]) == []
    assert any("X-Rite ColorMunki" in ln and ln.startswith("[NOTE]")
               for ln in lines)


def test_the_floor_keeps_f_where_it_works(tmp_path):
    from workflow.profile_builder import ProfileBuilder, ProfileParams
    ti3 = _ti3(tmp_path, "X-Rite i1 Pro 2")
    p = ProfileParams(ti3_path=ti3, fwa_enabled=True, fwa_illum="D50",
                      extra_args="-f")
    assert _fwa_in(ProfileBuilder(None)._build_args(p)) == ["-fD50", "-f"]
    assert without_refused_fwa(p) == (p, None)


def test_the_check_floor_drops_f_without_spectra(tmp_path):
    from workflow.profcheck_runner import ProfcheckParams, ProfcheckRunner
    ran, lines = [], []

    class _Runner:
        _settings = {}

        def run(self, tool, args, cwd=None, **k):
            ran.append(list(args))

    ti3 = _ti3(tmp_path, "CR30", spectra=False)
    ProfcheckRunner(_Runner()).run(
        ProfcheckParams(ti3_path=ti3, icc_path=tmp_path / "p.icc",
                        fwa_enabled=True),
        on_line=lines.append, on_finish=lambda code: None)
    assert ran and _fwa_in(ran[0]) == []
    assert any("no spectral readings" in ln for ln in lines)


def test_the_engine_floor_drops_f(tmp_path, monkeypatch):
    from workflow import engine_builder
    from workflow.profile_builder import ProfileParams
    seen = {}

    def _settings_from(params):
        seen["fwa"] = params.fwa_enabled
        raise ValueError("stop here")
    monkeypatch.setattr(engine_builder, "settings_from_params", _settings_from)
    lines = []
    engine_builder.EngineProfileBuilder().build(
        ProfileParams(ti3_path=_ti3(tmp_path, "i1iSis"), fwa_enabled=True),
        lines.append, lambda code: None)
    assert seen["fwa"] is False
    assert any("i1iSis" in ln and ln.startswith("[NOTE]") for ln in lines)


# ---------------------------------------------------------------------------
# The tabs: greyed with the reason, the tick kept, -f never passed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name, spectra, condition, kind", [
    ("X-Rite ColorMunki", True, None, "colormunki"),
    ("CR30", False, None, "no_spectra"),
    ("i1iSis", True, "M0", "instrument"),
    ("X-Rite i1 Pro 3", True, "M1", "condition"),
])
def test_build_profile_greys_fwa_with_the_reason_and_keeps_the_tick(
        qapp, tmp_path, monkeypatch, name, spectra, condition, kind):
    tab, _ = _profile_tab(tmp_path, monkeypatch)
    tab._fwa_check.setChecked(True)
    tab._m_fwa_check.setChecked(True)
    ti3 = _ti3(tmp_path, name, spectra=spectra, condition=condition)
    tab.set_ti3_path(ti3)
    reason = fwa_refusal_for_file(ti3).reason
    assert fwa_refusal_for_file(ti3).kind == kind
    for w in (tab._fwa_check, tab._fwa_illum_combo,
              tab._m_fwa_check, tab._m_fwa_illum_combo):
        assert not w.isEnabled()
        assert w.toolTip() == reason
    assert tab._fwa_check.isChecked() and tab._m_fwa_check.isChecked(), \
        "the gate only greys: a saved setting keeps the user's choice"
    for mode in ("guided", "manual"):
        tab._switch_mode(mode)
        assert tab._collect_params().fwa_enabled is False
        tab.refresh_argyll_commands(every=True)
        box = tab._guided_cmd_box if mode == "guided" else tab._manual_cmd_box
        assert " -f" not in box.text()
    tab.deleteLater()


def _build(tab, monkeypatch):
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


def test_build_profile_builds_a_colormunki_measurement_without_f(
        qapp, tmp_path, monkeypatch):
    tab, calls = _profile_tab(tmp_path, monkeypatch)
    tab._switch_mode("manual")
    tab._m_fwa_check.setChecked(True)
    tab.set_ti3_path(_ti3(tmp_path, "X-Rite ColorMunki"))
    _build(tab, monkeypatch)
    assert [c[0] for c in calls] == ["colprof"]
    assert _fwa_in(calls[0][1]) == []
    assert "[NOTE] FWA compensation (-f) was left out" in tab._log.toPlainText()
    tab.deleteLater()


@pytest.mark.parametrize("name", ["GretagMacbeth i1 Pro", "X-Rite i1 Pro 3",
                                  "GretagMacbeth SpectroScan"])
def test_build_profile_is_unchanged_where_fwa_works(
        qapp, tmp_path, monkeypatch, name):
    """Enabled, no tooltip of the gate, the combo follows its box, and -f
    reaches the command box and colprof."""
    tab, calls = _profile_tab(tmp_path, monkeypatch)
    plain = {id(w): w.toolTip() for w in (tab._fwa_check, tab._m_fwa_check,
                                         tab._fwa_illum_combo,
                                         tab._m_fwa_illum_combo)}
    tab.set_ti3_path(_ti3(tmp_path, name, condition="M0"))
    for box, combo in ((tab._fwa_check, tab._fwa_illum_combo),
                       (tab._m_fwa_check, tab._m_fwa_illum_combo)):
        assert box.isEnabled() and not combo.isEnabled()
        box.setChecked(True)
        assert combo.isEnabled()
        assert box.toolTip() == plain[id(box)]
        assert combo.toolTip() == plain[id(combo)]
    tab._switch_mode("manual")
    assert tab._collect_params().fwa_enabled is True
    tab.refresh_argyll_commands(every=True)
    assert " -f" in tab._manual_cmd_box.text()
    _build(tab, monkeypatch)
    assert [c[0] for c in calls] == ["colprof"]
    assert _fwa_in(calls[0][1]) != []
    assert "was left out" not in tab._log.toPlainText()
    tab.deleteLater()


def test_loading_a_good_measurement_after_a_refused_one_ungreys_it(
        qapp, tmp_path, monkeypatch):
    tab, _ = _profile_tab(tmp_path, monkeypatch)
    plain = tab._m_fwa_check.toolTip()
    tab.set_ti3_path(_ti3(tmp_path, "X-Rite ColorMunki", "a"))
    assert not tab._m_fwa_check.isEnabled()
    tab.set_ti3_path(_ti3(tmp_path, "GretagMacbeth i1 Pro", "b"))
    assert tab._m_fwa_check.isEnabled()
    assert tab._m_fwa_check.toolTip() == plain
    tab.deleteLater()


def test_check_refine_greys_fwa_without_spectra_and_keeps_it_for_an_i1pro(
        qapp, tmp_path, monkeypatch):
    tab, _ = _check_tab(tmp_path, monkeypatch)
    tab._fwa_cb.setChecked(True)
    tab._m_fwa_cb.setChecked(True)
    icc = tmp_path / "p.icc"
    icc.write_bytes(b"\0" * 128)
    ti3 = _ti3(tmp_path, "CR30", "cr", spectra=False)
    tab.set_paths(ti3, icc, propagate=False)
    reason = fwa_refusal_for_file(ti3).reason
    for w in (tab._fwa_cb, tab._fwa_combo, tab._m_fwa_cb, tab._m_fwa_combo):
        assert not w.isEnabled() and w.toolTip() == reason
    assert tab._fwa_cb.isChecked() and tab._m_fwa_cb.isChecked()
    assert tab._collect_params().fwa_enabled is False
    tab.set_paths(_ti3(tmp_path, "GretagMacbeth i1 Pro", "ok"), icc,
                  propagate=False)
    for box, combo in ((tab._fwa_cb, tab._fwa_combo),
                       (tab._m_fwa_cb, tab._m_fwa_combo)):
        assert box.isEnabled() and combo.isEnabled()
    assert tab._collect_params().fwa_enabled is True
    tab.deleteLater()
