"""The options audit harness forwards every Build Profile option (Agent 10b).

PART 2 of the options audit builds each option through the app's own route
(``build_worker`` ``params`` jobs). These tests keep that honest without a
hand-kept list: every ``ProfileParams`` field reaches the job, an unknown key
is refused, every field the Manual tab sets is exercised by the options
matrix, and each field either changes what a builder is handed or is on the
short, named list of fields that do nothing for that builder.
"""
from __future__ import annotations

import dataclasses
import importlib.util
from pathlib import Path

import pytest

from workflow.engine_builder import settings_from_params
from workflow.profile_builder import ProfileBuilder, ProfileParams

ROOT = Path(__file__).resolve().parents[1]

# Scanner window only (input-profile white point), or not a user option.
NOT_ON_THE_BUILD_TAB = {"ti3_path", "wp_mode", "wp_scale", "clip_primaries",
                        "extra_args", "verbose"}
# Fields that change nothing for one builder, and why (each is a finding of
# the audit, not an accident of the test).
ENGINE_NO_OP = {
    "dark_emphasis": "colprof -V: no effect for printer data in colprof either",
    "verbose": "the engine always logs",
    "k_stle": "only with k_rule p", "k_stpo": "only with k_rule p",
    "k_enpo": "only with k_rule p", "k_enle": "only with k_rule p",
    "k_shape": "only with k_rule p",
}
COLPROF_NO_OP = {
    "spectral_physics": "engine-only option",
    "icc_version": "engine-only option",
    "noise_model": "engine-only option",
    "render_style": "engine-only option",
    "k_locus": "only together with a k_rule",
    "k_stle": "only with k_rule p", "k_stpo": "only with k_rule p",
    "k_enpo": "only with k_rule p", "k_enle": "only with k_rule p",
    "k_shape": "only with k_rule p",
    "fwa_illum": "only with fwa_enabled",
}


def _worker():
    spec = importlib.util.spec_from_file_location(
        "build_worker", ROOT / "benchmarks" / "research" / "build_worker.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _changed(field: dataclasses.Field):
    d = field.default
    if isinstance(d, bool):
        return not d
    if isinstance(d, float):
        return d + 1.25 if field.name != "smoothing" else 2.0
    if field.name in ("algorithm",):
        return "x"
    if field.name in ("quality",):
        return "h"
    if field.name == "b2a_quality":
        return "h"
    if field.name == "icc_version":
        return "4"
    if field.name == "render_style":
        return "bijective"
    if field.name == "k_rule":
        return "x"
    if field.name.startswith("z_") and field.name != "z_default_intent":
        return {"z_surface": "m", "z_media_type": "t", "z_polarity": "n",
                "z_color_mode": "b"}[field.name]
    if field.name == "z_default_intent":
        return "p"
    if field.name in ("perc_intent",):
        return "pa"
    if field.name in ("sat_intent",):
        return "ms"
    if field.name in ("src_viewing_cond", "dst_viewing_cond"):
        return "mt"
    if field.name in ("illuminant",):
        return "D65"
    if field.name in ("observer",):
        return "1964_10"
    if field.name in ("fwa_illum",):
        return "D50"
    if field.name in ("gamut_src", "gamut_sat_src"):
        return "/x/ClayRGB1998.icm"
    return "Something"


def _fields():
    return [f for f in dataclasses.fields(ProfileParams) if f.name not in NOT_ON_THE_BUILD_TAB]


def test_worker_refuses_a_key_that_is_not_a_profileparams_field(tmp_path):
    w = _worker()
    with pytest.raises(KeyError):
        w._params({"ti3": str(tmp_path / "a.ti3"), "params": {"no_such_option": 1}})
    p = w._params({"ti3": str(tmp_path / "a.ti3"), "params": {"quality": "h"}})
    assert p.quality == "h" and p.ti3_path == tmp_path / "a.ti3"


@pytest.mark.parametrize("field", _fields(), ids=lambda f: f.name)
def test_every_field_reaches_the_engine_or_is_a_named_no_op(field, tmp_path):
    ti3 = tmp_path / "m.ti3"
    base = ProfileParams(ti3_path=ti3)
    other = dataclasses.replace(base, **{field.name: _changed(field)})
    a, b = settings_from_params(base), settings_from_params(other)
    strip = lambda s: {k: v for k, v in dataclasses.asdict(s).items()  # noqa: E731
                       if k != "progress"}
    if field.name in ENGINE_NO_OP:
        assert strip(a) == strip(b), field.name
    else:
        assert strip(a) != strip(b), f"{field.name} does not reach BuildSettings"


@pytest.mark.parametrize("field", _fields(), ids=lambda f: f.name)
def test_every_field_reaches_colprof_or_is_a_named_no_op(field, tmp_path):
    ti3 = tmp_path / "m.ti3"
    ti3.write_text("CTI3\n", encoding="utf-8")
    pb = ProfileBuilder.__new__(ProfileBuilder)
    base = ProfileParams(ti3_path=ti3)
    other = dataclasses.replace(base, **{field.name: _changed(field)})
    if field.name in COLPROF_NO_OP:
        assert pb._build_args(base) == pb._build_args(other), field.name
    else:
        assert pb._build_args(base) != pb._build_args(other), \
            f"{field.name} does not reach the colprof command"


def test_the_options_matrix_exercises_every_build_tab_field():
    from benchmarks.research.options import matrix
    seen = set()
    for row in matrix():
        seen |= set(row["params"])
    missing = {f.name for f in _fields()} - seen
    # fwa_illum is exercised (S3 "fD50"); every other field must be too
    assert not missing, f"options never set by the audit: {sorted(missing)}"


def test_every_dataset_a_build_or_job_names_is_scoreable():
    """The analysis step looks each job's dataset up in DATASETS: a name the
    matrix uses (or COLPROF_OK lists) that is missing there raised
    KeyError 'X1p' after 179 builds."""
    from benchmarks.research.options import DATASETS, COLPROF_OK, matrix
    used = {row["ds"] for row in matrix()}
    assert used <= set(DATASETS), sorted(used - set(DATASETS))
    assert COLPROF_OK <= set(DATASETS), sorted(COLPROF_OK - set(DATASETS))
