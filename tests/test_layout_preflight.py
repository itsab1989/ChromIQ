"""Tests for the headless pre-flight checks."""
from workflow.layout_engine import geometry, instruments, preflight


def test_clean_layout_ok():
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, 60)
    rep = preflight.check(geom, lay)
    assert rep.ok
    assert not rep.errors
    assert rep.info


def test_low_contrast_warns_but_ok():
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, 60)
    rep = preflight.check(geom, lay, low_contrast_passes=[2, 5])
    assert rep.ok                       # warning, not a hard fail
    assert rep.warnings
    assert rep.warnings[0].startswith("strips 3, 6:")


def test_indicator_width_warning():
    geom = instruments.build("i1")
    # auto size fits the strip → no warning
    assert preflight.indicator_width_warning(geom, 300, size_mm=0.0) is None
    # an explicit oversized indicator overflows the strip → warning
    assert preflight.indicator_width_warning(geom, 300, size_mm=12.0) is not None
    # hidden indicators never warn
    assert preflight.indicator_width_warning(geom, 300, size_mm=12.0, show=False) is None


def test_sub_minimum_patch_errors():
    # heavy down-scale pushes i1 patches below the 6 mm floor (plen 10*0.5=5)
    geom = instruments.build("i1", pscale=0.5)
    lay = geometry.compute(geom, 210.0, 297.0, 60)
    rep = preflight.check(geom, lay)
    assert not rep.ok
    assert any("reliability floor" in e for e in rep.errors)
