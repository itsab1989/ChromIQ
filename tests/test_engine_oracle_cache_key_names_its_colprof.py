"""Expert review 2026-11-10: the colprof reference ("oracle") cache key.

The engine keeps the rendering it matched to ArgyllCMS colprof for the
session, keyed on the measurement and the oracle's command line. Three inputs
reached the oracle without being in that key:

* WHICH colprof ran. After the ArgyllCMS folder is changed in Preferences
  (another version, a repaired install), a rebuild of the same measurement
  reused the rendering of the colprof that is no longer selected;
* the gamut source FILE. Only its path was keyed, so a profile replaced under
  the same name kept the old rendering;
* whether the oracle profile's bytes were kept for a86-knutdark. A result
  cached without them silently switched that token off for the next build.
"""
import os
from pathlib import Path
from types import SimpleNamespace

from workflow.profile_engine import gamut_map


def _settings(**kw):
    base = dict(quality="h", sat_gamut=True, perc_intent="", sat_intent="",
                src_viewing="", dst_viewing="", perc_src_colorimetric=False,
                sat_src_colorimetric=False, illuminant="", observer="",
                fwa=False, fwa_illum="", k_rule="", k_locus=False,
                k_curve_params=None, engine_candidates=frozenset(),
                argyll_bin=None)
    base.update(kw)
    return SimpleNamespace(**base)


def _meas(tmp_path):
    p = tmp_path / "m.ti3"
    p.write_text("CTI3\n", encoding="utf-8")
    return SimpleNamespace(path=p)


def _argyll(folder: Path, body: str) -> Path:
    folder.mkdir()
    for name in ("colprof", "xicclu", "colprof.exe", "xicclu.exe"):
        (folder / name).write_text(body, encoding="utf-8")
    return folder


def test_another_argyll_folder_is_another_key(tmp_path):
    meas = _meas(tmp_path)
    src = tmp_path / "src.icc"
    src.write_bytes(b"one")
    a = _argyll(tmp_path / "argyll-a", "a")
    b = _argyll(tmp_path / "argyll-b", "b")
    key = gamut_map._oracle_cache_key
    k_a = key(meas, src, _settings(), None, a)
    assert k_a == key(meas, src, _settings(), None, a)
    assert k_a != key(meas, src, _settings(), None, b)
    # the folder named in the settings counts when none is passed
    assert key(meas, src, _settings(argyll_bin=a), None) == k_a
    assert key(meas, src, _settings(argyll_bin=b), None) != k_a


def test_a_replaced_colprof_in_the_same_folder_is_another_key(tmp_path):
    meas = _meas(tmp_path)
    src = tmp_path / "src.icc"
    src.write_bytes(b"one")
    a = _argyll(tmp_path / "argyll", "version one")
    before = gamut_map._oracle_cache_key(meas, src, _settings(), None, a)
    for name in ("colprof", "colprof.exe"):
        (a / name).write_text("version two, longer", encoding="utf-8")
    assert gamut_map._oracle_cache_key(meas, src, _settings(), None,
                                       a) != before


def test_a_replaced_gamut_source_file_is_another_key(tmp_path):
    meas = _meas(tmp_path)
    src = tmp_path / "src.icc"
    src.write_bytes(b"one")
    a = _argyll(tmp_path / "argyll", "a")
    before = gamut_map._oracle_cache_key(meas, src, _settings(), None, a)
    src.write_bytes(b"another profile")
    st = src.stat()
    os.utime(src, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    assert gamut_map._oracle_cache_key(meas, src, _settings(), None,
                                       a) != before


def test_a_result_kept_without_the_oracle_profile_is_not_reused_with_a86(
        tmp_path):
    meas = _meas(tmp_path)
    src = tmp_path / "src.icc"
    src.write_bytes(b"one")
    a = _argyll(tmp_path / "argyll", "a")
    without = gamut_map._oracle_cache_key(meas, src, _settings(), None, a)
    with_a86 = gamut_map._oracle_cache_key(
        meas, src,
        _settings(engine_candidates=frozenset({gamut_map.A86_TOKEN})),
        None, a)
    assert without != with_a86


def test_a_missing_argyll_folder_still_gives_a_key(tmp_path):
    meas = _meas(tmp_path)
    key = gamut_map._oracle_cache_key(meas, tmp_path / "no.icc", _settings(),
                                      None, tmp_path / "nowhere")
    assert key is not None
