"""The bit-exact gamut-mapping helper bridge + its mode plumbing.

Covers the Python side of the "Bit-exact (Argyll's engine)" option: locating
the bundled ``chromiq-gammap`` binary, the subprocess contract, graceful
absence, the quality→resolution table, and the settings migration that retires
the old boolean toggle. The heavy end-to-end build (Argyll's real mapper on a
CMY+N shell) is exercised by the engine build tests; here we keep to fast,
binary-optional units so CI stays green whether or not the helper is compiled.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from PyQt6.QtCore import QSettings

from tests.argyll_env import argyll_tool
from workflow.profile_engine import gammap_helper as gh


# --- quality → (gres, mapres), matching colprof (profout.c) -----------------

@pytest.mark.parametrize("q,gres,mapres", [
    ("u", 7.0, 49), ("h", 8.0, 39), ("m", 10.0, 29), ("l", 12.0, 19),
])
def test_gres_mapres_table(q, gres, mapres):
    assert gh.gres_mapres_for_quality(q) == (gres, mapres)


def test_gres_mapres_unknown_defaults_medium():
    assert gh.gres_mapres_for_quality("") == gh.gres_mapres_for_quality("m")
    assert gh.gres_mapres_for_quality("zzz") == (10.0, 29)


# --- helper location + graceful absence -------------------------------------

def test_missing_binary_reports_unavailable(monkeypatch, tmp_path):
    monkeypatch.setenv("CHROMIQ_GAMMAP", str(tmp_path / "nope"))
    assert gh.is_available() is False
    with pytest.raises(gh.HelperUnavailable):
        gh.helper_path()


def test_env_override_locates_binary(monkeypatch, tmp_path):
    fake = tmp_path / "chromiq-gammap"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("CHROMIQ_GAMMAP", str(fake))
    assert gh.is_available() is True
    assert gh.helper_path() == fake


def test_run_gammap_missing_binary_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("CHROMIQ_GAMMAP", str(tmp_path / "nope"))
    with pytest.raises(gh.HelperUnavailable):
        gh.run_gammap(np.zeros((2, 3)), src_gam="x.gam", intent="p",
                      mapres=29, dst_gam="d.gam")


def test_run_gammap_rejects_both_dst(monkeypatch, tmp_path):
    fake = tmp_path / "chromiq-gammap"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("CHROMIQ_GAMMAP", str(fake))
    with pytest.raises(gh.HelperUnavailable):
        gh.run_gammap(np.zeros((1, 3)), src_gam="s.gam", intent="p",
                      mapres=29, dst_gam="d.gam",
                      dst_cloud_jab=np.zeros((4, 3)))


# --- settings migration: retire the legacy boolean --------------------------

def test_migration_drops_legacy_gammap_key(tmp_path):
    from core.settings import AppSettings, SETTINGS_SCHEMA

    ini = str(tmp_path / "s.ini")
    seed = QSettings(ini, QSettings.Format.IniFormat)
    seed.setValue("gammap_exact_geometry", True)
    seed.setValue("settings_schema", 5)
    seed.sync()

    app = AppSettings()
    app._qs = QSettings(ini, QSettings.Format.IniFormat)
    dropped = app.migrate()

    assert "gammap_exact_geometry" in dropped
    assert app._qs.value("gammap_exact_geometry", None) is None
    assert SETTINGS_SCHEMA >= 6
    assert int(app._qs.value("settings_schema")) == SETTINGS_SCHEMA


def test_the_mode_picker_has_no_setting_any_more():
    """Since 2026-11-10 the app builds with one engine mode; the helper is
    still what a multi-ink build's gamut mapping runs through. The switch and
    the migration: tests/test_the_new_profile_engine_is_one_switch.py."""
    from core.settings import DEFAULTS
    assert "gammap_mode" not in DEFAULTS


# --- optional integration: the real binary round-trips ----------------------

def _built_binary() -> str | None:
    """A compiled chromiq-gammap, if one exists (env or a local build)."""
    env = os.environ.get("CHROMIQ_GAMMAP")
    if env and Path(env).exists():
        return env
    return None


# --- CMYK dest-gamut fallback: iccgamut can't read an A2B-only 4-ink ICC ----

def test_argyll_cmyk_falls_back_to_cloud(monkeypatch, tmp_path):
    """<=4-ink argyll path: when iccgamut fails on the temp CMYK ICC (xicc
    needs an inverse for 4 channels), the destination gamut is sampled from the
    model cloud instead of silently deferring to the colprof oracle."""
    from workflow.profile_engine.gammap_port import wire
    from workflow.profile_engine.forward_model import fit_forward_model

    fake = tmp_path / "chromiq-gammap"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("CHROMIQ_GAMMAP", str(fake))

    rng = np.random.default_rng(0)
    dev = rng.random((80, 4))
    lab = np.column_stack([
        100 - 60 * dev[:, 3] - 20 * dev[:, 0],
        40 * (dev[:, 1] - dev[:, 0]),
        40 * (dev[:, 2] - dev[:, 1])])
    model = fit_forward_model(dev, lab, grid=5, lam=0.05, curve_rounds=0)

    clay = Path(__file__).resolve().parent.parent / "assets/profiles/ClayRGB1998.icm"

    def fake_iccgamut(path, work_icc, bin_dir, detail):
        if "dest" in Path(path).name:           # simulate the CMYK failure
            raise wire.PortUnavailable("simulated iccgamut CMYK failure")
        return Path(path)                        # pretend the source .gam built

    monkeypatch.setattr(wire, "_iccgamut_to", fake_iccgamut)

    meas = type("M", (), {"color_rep": "CMYK_XYZ", "n_channels": 4})()
    settings = type("S", (), {"quality": "l"})()
    # bin_dir is never dereferenced here — _iccgamut_to is stubbed above.
    out = wire.fit_gammap_argyll_mappers(
        model, meas, clay, settings, Path("unused-bin-dir"),
        is_additive=False, ink_limit=None)

    assert set(out) == {"B2A0", "B2A2"}
    m = out["B2A0"]
    assert m._dst_gam is None            # not the .gam path
    assert m._dst_cloud is not None      # the model-sampled cloud instead
    assert m._wp_jab is not None         # cloud path needs explicit wp/bp


@pytest.mark.skipif(
    _built_binary() is None or argyll_tool("iccgamut") is None,
    reason="needs a compiled chromiq-gammap and iccgamut",
)
def test_helper_roundtrip_dst_gam(tmp_path):
    """Grey stays neutral through Argyll's real mapper (sanity, not exactness)."""
    profiles = Path(__file__).resolve().parent.parent / "assets/profiles"

    def _gam(name: str, stem: str) -> Path:
        work = tmp_path / (stem + Path(name).suffix)
        shutil.copy(profiles / name, work)
        subprocess.run([argyll_tool("iccgamut"), "-ff", "-ir", "-pj", "-d10",
                        work.name], cwd=tmp_path, check=True, capture_output=True)
        gam = work.with_suffix(".gam")
        assert gam.exists()
        return gam

    src_gam = _gam("ClayRGB1998.icm", "src")   # wide source
    dst_gam = _gam("sRGB.icm", "dst")          # smaller, distinct destination

    query = np.array([[50.0, 0.0, 0.0], [70.0, 0.0, 0.0]])
    out = gh.run_gammap(query, src_gam=src_gam, intent="p", mapres=29,
                        dst_gam=dst_gam)
    assert out.shape == query.shape
    # neutral in → near-neutral out (small a/b)
    assert np.all(np.abs(out[:, 1:]) < 5.0)
