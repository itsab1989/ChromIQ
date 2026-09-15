"""The from-profile-gamut chart asks for the NUMERIC inverse, not the baked one.

`xicclu -fb` reads the profile's B2A table, which is a fast approximation of an
inverse. `-fif` inverts the forward table numerically. `backward_device` could
only reach `-fif` by being handed an ink limit, and an ink limit is meaningless
on an RGB output profile, so every RGB caller silently took the approximation.

Measured over the app's own eleven bundled reference sets, 792 patches, each Lab
aim inverted to device values and put back through the same profile:

    -fb    0.366 mean dE00, 659 of 792 within 0.5
    -fif   0.052 mean dE00, 770 of 792 within 0.5

These device values are printed on paper and then measured against those aims,
so the error goes straight into the verification. The cost of the accurate path
is 0.17 s for 1,617 patches.
"""
from __future__ import annotations

import inspect
import subprocess

import pytest

from workflow import gamut_target, xicclu_runner as X


_XICCLU = "xicclu"


class _Spy:
    """Stands in for `subprocess.run`, keeping the argument list.

    The canned line is xicclu's real shape, taken from
    `tests/test_xicclu_runner.py`, because the parser rejects anything else and
    a test that cannot get past the parser proves nothing about the flags.
    """

    def __init__(self, rows: int = 1) -> None:
        self.calls: list[list[str]] = []
        self._rows = rows

    def __call__(self, cmd, **kw):
        self.calls.append(list(cmd))
        line = ("50.000000 10.000000 -5.000000 [Lab] -> Lut -> "
                "0.126686 0.742860 0.733718 [RGB]")
        body = "\n".join(line for _ in range(self._rows)) + "\n"
        return subprocess.CompletedProcess(cmd, 0, stdout=body, stderr="")

    @property
    def flags(self) -> list[str]:
        return [a for c in self.calls for a in c]


# --- the switch itself ------------------------------------------------------

def test_the_numeric_inverse_can_be_asked_for_without_an_ink_limit(tmp_path):
    spy = _Spy()
    (tmp_path / _XICCLU).touch()
    X.backward_device([(50.0, 10.0, -5.0)], tmp_path / "p.icc", tmp_path,
                      numeric_inverse=True, runner=spy)
    assert "-fif" in spy.flags
    assert "-fb" not in spy.flags
    assert not [f for f in spy.flags if f.startswith("-l")], (
        "asking for accuracy must not smuggle in an ink limit")


def test_the_fast_table_is_still_the_default(tmp_path):
    spy = _Spy()
    (tmp_path / _XICCLU).touch()
    X.backward_device([(50.0, 10.0, -5.0)], tmp_path / "p.icc", tmp_path,
                      runner=spy)
    assert "-fb" in spy.flags and "-fif" not in spy.flags


def test_an_ink_limit_still_forces_the_numeric_inverse(tmp_path):
    """The older reason for `-fif`, which must survive: only that path
    enforces `-l`, so a CMYK caller with a limit still gets it."""
    spy = _Spy()
    (tmp_path / _XICCLU).touch()
    X.backward_device([(50.0, 10.0, -5.0)], tmp_path / "p.icc", tmp_path,
                      ink_limit=250.0, runner=spy)
    assert "-fif" in spy.flags
    assert "-l250" in spy.flags


# --- and the caller that puts the answer on paper ---------------------------

def test_the_one_round_trip_asks_for_the_numeric_inverse():
    """Read at the call site rather than driven, because driving it needs a
    real profile and ArgyllCMS; what must not regress is the ARGUMENT."""
    src = inspect.getsource(gamut_target._round_trip)
    assert "numeric_inverse=True" in src, (
        "the gamut round trip inverts through the baked B2A table again; a "
        "chart built that way lands 0.366 dE00 from its own aims instead of "
        "0.052")


@pytest.mark.parametrize("fn", ["select_gamut_targets", "flags_in_gamut"])
def test_neither_entry_point_inverts_behind_the_round_trips_back(fn):
    """Both entry points go through `_round_trip` and neither reaches for
    xicclu itself.

    Stronger than asking each of them for `numeric_inverse=True` separately,
    which is what this checked while they each had their own copy of the call:
    a second copy could drift to `-fb` on its own, and now there is nowhere for
    a second copy to live.
    """
    src = inspect.getsource(getattr(gamut_target, fn))
    assert "_round_trip(" in src, (
        f"{fn} no longer shares the one round trip, so the question it asks "
        "the profile can drift from the other entry point's")
    assert "backward_device(" not in src, (
        f"{fn} inverts on its own again instead of going through _round_trip")


def test_no_gamut_target_call_site_is_left_on_the_fast_table():
    """Both call sites, counted, so a third added later cannot be missed."""
    src = inspect.getsource(gamut_target)
    calls = src.count("backward_device(")
    asked = src.count("numeric_inverse=True")
    assert calls == asked, (
        f"{calls} inversions in gamut_target and only {asked} ask for the "
        "numeric one")
