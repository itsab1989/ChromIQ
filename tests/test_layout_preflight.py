"""Tests for the headless pre-flight checks."""
from workflow.layout_engine import geometry, instruments, preflight


def test_clean_layout_ok():
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, 60)
    rep = preflight.check(geom, lay)
    assert rep.ok
    assert not rep.errors
    assert rep.info


def test_the_dead_low_contrast_branch_is_gone():
    """No caller in the app passed the strips, so the English-only warning
    could never be shown (review 4.3.19 r1, N7); the note a person sees is the
    Create Chart log line."""
    import inspect
    assert "low_contrast_passes" not in inspect.signature(preflight.check).parameters
    src = inspect.getsource(preflight)
    assert "a very dark patch" not in src


def test_indicator_width_warning():
    geom = instruments.build("i1")
    # auto size fits the strip → no warning
    assert preflight.indicator_width_warning(geom, 300, size_mm=0.0) is None
    # an explicit oversized indicator overflows the strip → warning
    assert preflight.indicator_width_warning(geom, 300, size_mm=12.0) is not None
    # hidden indicators never warn
    assert preflight.indicator_width_warning(geom, 300, size_mm=12.0, show=False) is None


def test_sub_minimum_patch_errors():
    # heavy down-scale pushes i1 patches below the 6 mm floor (4 x 5 mm)
    geom = instruments.build("i1", pscale=0.5)
    lay = geometry.compute(geom, 210.0, 297.0, 60)
    rep = preflight.check(geom, lay)
    assert not rep.ok
    assert any("smaller than the 6.0 mm" in e and "4.0 mm" in e
               for e in rep.errors)
    assert not any("—" in e for e in rep.errors)


def test_the_shown_texts_are_translated(monkeypatch):
    """Preferences > Chart Layout shows these two texts, so they go through
    tr() and the German catalogue has them."""
    import json
    from pathlib import Path
    import core.i18n as i18n
    de = json.loads((Path(__file__).resolve().parents[1]
                     / "data/i18n/de.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(i18n, "tr", lambda s: de.get(s, s))
    geom = instruments.build("i1", pscale=0.5)
    lay = geometry.compute(geom, 210.0, 297.0, 60)
    err = preflight.check(geom, lay).errors[0]
    assert "Feldskalierung" in err and "{" not in err
    assert not err.startswith("The patches")
    warn = preflight.indicator_width_warning(instruments.build("i1"), 300,
                                             size_mm=12.0)
    assert warn and "{" not in warn
    assert not warn.startswith("The strip letters")
