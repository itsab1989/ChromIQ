"""Engine ↔ colprof routing (#122): support gate, multi-ink detection,
Qt build thread, settings round-trip.

The loss-free doctrine under test: the ChromIQ engine only ever takes a
build it fully covers; every colprof-only option pushes the build back to
colprof with a named reason; multi-ink measurements are engine-only.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

from tests.test_profile_engine import write_synth_ti3  # noqa: E402
from workflow.engine_builder import (EngineProfileBuilder, engine_support,
                                     is_multi_ink, ti3_device_rep)  # noqa: E402
from workflow.profile_builder import ProfileParams  # noqa: E402

_TI3_RGB = '''CTI3
COLOR_REP "iRGB_XYZ"
NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 1
BEGIN_DATA
1 100.0 100.0 100.0 96.4 100.0 82.5
END_DATA
'''


def _params(ti3: Path, **kw) -> ProfileParams:
    return ProfileParams(ti3_path=ti3, description="t", **kw)


# ---------------------------------------------------------------------------
# COLOR_REP detection
# ---------------------------------------------------------------------------

def test_multi_ink_detection(tmp_path):
    rgb = tmp_path / "rgb.ti3"
    rgb.write_text(_TI3_RGB, encoding="utf-8")
    assert ti3_device_rep(rgb) == "iRGB"
    assert not is_multi_ink(rgb)
    og = tmp_path / "og.ti3"
    og.write_text(_TI3_RGB.replace('"iRGB_XYZ"', '"CMYKOG_XYZ"'), encoding="utf-8")
    assert is_multi_ink(og)
    cmyk = tmp_path / "c.ti3"
    cmyk.write_text(_TI3_RGB.replace('"iRGB_XYZ"', '"CMYK_XYZ"'), encoding="utf-8")
    assert not is_multi_ink(cmyk)          # colprof covers CMYK
    assert not is_multi_ink(tmp_path / "missing.ti3")


# ---------------------------------------------------------------------------
# Loss-free support gate
# ---------------------------------------------------------------------------

def test_engine_support_defaults_pass(tmp_path):
    ok, why = engine_support(_params(tmp_path / "x.ti3"))
    assert ok and why == ""


def test_engine_support_known_gamut_sources(tmp_path):
    ok, _ = engine_support(_params(tmp_path / "x.ti3",
                                   gamut_src="/ref/ClayRGB1998.icm"))
    assert ok
    ok, why = engine_support(_params(tmp_path / "x.ti3",
                                     gamut_src="/ref/ProPhoto.icm"))
    assert not ok and "gamut source" in why


@pytest.mark.parametrize("kw", [
    dict(fwa_enabled=True),
    dict(illuminant="D50"),
    dict(observer="1964_10"),
    dict(smoothing=2.0),
    dict(dark_emphasis=2.0),           # no-op for output class, like colprof
    dict(no_input_shaper=True),
    dict(no_output_shaper=True),
    dict(no_grid_pos=True),
    dict(no_embedded_data=True),
    dict(b2a_quality="h"),
    dict(algorithm="x"),
    dict(src_viewing_cond="pp"),
    dict(dst_viewing_cond="mt"),
    dict(perc_intent="la"),
    dict(sat_intent="ms"),
    dict(no_perc_gamut=True),
    dict(no_sat_gamut=True),
    dict(inv_gamut_map=True),
    dict(clip_primaries=True),
    dict(z_surface="m"),
    dict(z_default_intent="s"),
    dict(manufacturer="Epson", model="ET-8550"),
    dict(wp_mode="scale", wp_scale=0.98),
    dict(extra_args="-r 1.2 -nI -fD50 -Zm -l 260"),
])
def test_engine_supports_full_colprof_surface(tmp_path, kw):
    """After the superset round every UI-reachable option is engine-covered."""
    ok, why = engine_support(_params(tmp_path / "x.ti3", **kw))
    assert ok, why


def test_engine_support_unknown_extra_flag_names_it(tmp_path):
    ok, why = engine_support(_params(tmp_path / "x.ti3", extra_args="-y 1.3"))
    assert not ok and "-y" in why


def test_extra_args_fold_into_settings(tmp_path):
    from workflow.engine_builder import settings_from_params
    s = settings_from_params(_params(
        tmp_path / "x.ti3",
        extra_args='-r 1.5 -b l -fD65 -Zm -Zs -A "ACME Inc" -l 250 -nI'))
    assert s.smoothing == 1.5
    assert s.b2a_quality == "l"
    assert s.fwa and s.fwa_illum == "D65"
    assert s.z_attributes == "m" and s.z_default_intent == "s"
    assert s.manufacturer == "ACME Inc"
    assert s.ink_limit == 250.0
    assert s.inverse_gamut_a2b


def test_wp_modes_error_like_colprof(tmp_path):
    """-u/-ua/-uc error on output data in colprof — the engine mirrors it."""
    from workflow.engine_builder import settings_from_params
    for mode in ("u", "ua", "uc"):
        with pytest.raises(ValueError, match="output device"):
            settings_from_params(_params(tmp_path / "x.ti3", wp_mode=mode))
    # but they are not a routing gate: the engine reports the same failure
    ok, _ = engine_support(_params(tmp_path / "x.ti3", wp_mode="u"))
    assert ok


def test_matrix_algorithm_errors_like_colprof(tmp_path, qtbot):
    """colprof: 'Output profile can only be a cLUT algorithm' — engine too."""
    ti3 = write_synth_ti3(tmp_path / "s.ti3", "iRGB",
                          ["RGB_R", "RGB_G", "RGB_B"], additive=True)
    builder = EngineProfileBuilder()
    finished: list[int] = []
    lines: list[str] = []
    builder.build(_params(ti3, algorithm="g"), on_line=lines.append,
                  on_finish=finished.append)
    qtbot.waitUntil(lambda: bool(finished), timeout=30000)
    assert finished == [1]
    assert any("cLUT" in ln for ln in lines)


# ---------------------------------------------------------------------------
# The Qt build thread, end to end on a synthetic measurement
# ---------------------------------------------------------------------------

def test_engine_builder_builds_profile(tmp_path, qtbot):
    ti3 = write_synth_ti3(tmp_path / "s.ti3", "iRGB",
                          ["RGB_R", "RGB_G", "RGB_B"], additive=True)
    builder = EngineProfileBuilder()
    params = _params(ti3, quality="l")
    lines: list[str] = []
    finished: list[int] = []
    builder.build(params, on_line=lines.append, on_finish=finished.append)

    def done() -> bool:
        return bool(finished)
    qtbot.waitUntil(done, timeout=60000)
    assert finished == [0]
    icc = builder.expected_icc_path(params)
    assert icc == ti3.with_suffix(".icc") and icc.exists()
    assert any("ChromIQ profile engine" in ln for ln in lines)
    assert builder.primary_failure() is None


def test_engine_builder_reports_failure(tmp_path, qtbot):
    bad = tmp_path / "bad.ti3"
    bad.write_text("not a measurement", encoding="utf-8")
    builder = EngineProfileBuilder()
    finished: list[int] = []
    lines: list[str] = []
    builder.build(_params(bad), on_line=lines.append,
                  on_finish=finished.append)
    qtbot.waitUntil(lambda: bool(finished), timeout=30000)
    assert finished == [1]
    assert builder.primary_failure() is not None
    assert any("[ERROR]" in ln for ln in lines)


def test_thread_reference_is_held_until_the_thread_really_stops(qtbot, tmp_path):
    """The engine's QThread must stay referenced until Qt says it has finished.

    ``done`` is emitted from inside run(), so the thread is still going when the
    finish callback fires. Releasing the reference there left a LIVE QThread
    eligible for garbage collection, and Qt aborts the process if it collects
    one — an intermittent hard crash that killed a release gate twice. This pins
    the ordering: the reference survives the finish callback."""
    ti3 = write_synth_ti3(tmp_path / "s.ti3", "iRGB",
                          ["RGB_R", "RGB_G", "RGB_B"], additive=True)
    builder = EngineProfileBuilder()
    params = _params(ti3, quality="l")
    finished: list[int] = []
    held: list[bool] = []

    def _on_finish(code: int) -> None:
        # Called from the done signal — the thread must still be referenced.
        held.append(builder._thread is not None)
        finished.append(code)

    builder.build(params, on_line=lambda _l: None, on_finish=_on_finish)
    qtbot.waitUntil(lambda: bool(finished), timeout=60000)

    assert finished == [0]
    assert held == [True], "the QThread was released while still running"
    # and it is released once Qt reports the thread finished
    qtbot.waitUntil(lambda: builder._thread is None, timeout=10000)
    assert builder.is_running is False
