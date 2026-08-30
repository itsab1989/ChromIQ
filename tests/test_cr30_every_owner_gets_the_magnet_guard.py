"""The magnet guard must work on a CR30 that is not the owner's.

`TILE_SIGNATURE` is ONE unit's stored constant. The only other CR30 anyone has
measured reads its white reference up to 4.69 %R lower (PRIORART-001) -- 94x the
0.05 tolerance -- so on that unit the tile check matched nothing and its owner
had no magnet protection at all. A magnet at the aperture makes the instrument
hand back that constant instead of measuring, so the reading looks like a
perfectly ordinary patch colour and goes into the profile.

These drive the REAL Measurement guard and the REAL tile_learning store. The
only stand-in is the settings backend, which is the outermost edge; every
decision under test is made by the shipped code.
"""
import json

import pytest

from workflow.cr30 import tile_learning as tl
from workflow.cr30.measurement import (Measurement, MagnetGated,
                                       TILE_SIGNATURE)

#: The measured gap to the only other CR30 in evidence (PRIORART-001).
FOREIGN_GAP = 4.69
WAVELENGTHS = [400 + 10 * i for i in range(31)]


@pytest.fixture
def store(monkeypatch):
    """A settings store that lives only for this test."""
    kept: dict = {}

    class _Settings:
        def get(self, key, default=None):
            return kept.get(key, default)

        def set(self, key, value):
            kept[key] = value

    monkeypatch.setattr(tl, "_settings", lambda: _Settings())
    return kept


def _tile(offset=0.0):
    return [round(v - offset, 6) for v in TILE_SIGNATURE]


def _reading(values, **kw):
    return Measurement(wavelengths=WAVELENGTHS, values=list(values), **kw)


# -- the hole this closes ---------------------------------------------------

def test_a_foreign_units_gated_reading_is_accepted_as_a_patch_today():
    """The defect, stated as a test so it cannot come back unnoticed."""
    gated = _reading(_tile(FOREIGN_GAP))
    gated.check_usable()          # no learned signature: this is today
    # It passed. That reading is the tile constant, and it just became a patch.


def test_the_same_reading_is_refused_once_that_unit_has_learned():
    gated = _reading(_tile(FOREIGN_GAP))
    with pytest.raises(MagnetGated):
        gated.check_usable(learned_tile=_tile(FOREIGN_GAP))


def test_a_real_patch_still_passes_with_a_signature_armed():
    patch = _reading([40.0 + 0.7 * i for i in range(31)])
    patch.check_usable(learned_tile=_tile(FOREIGN_GAP))


def test_the_learned_check_is_tighter_than_the_built_in_one():
    """0.001 %R, not 0.05 -- so arming can only ever refuse fewer real patches."""
    near = _tile(FOREIGN_GAP)
    near[0] += 0.01               # inside 0.05, far outside 0.001
    _reading(near).check_usable(learned_tile=_tile(FOREIGN_GAP))
    with pytest.raises(MagnetGated):
        _reading(_tile(FOREIGN_GAP)).check_usable(
            learned_tile=_tile(FOREIGN_GAP))


# -- provenance: a value is learned only when it is PROVEN gated -------------

def test_a_usb_press_is_proof_when_the_device_flags_it():
    learner = tl.TileLearner()
    proven = learner.offer(_reading(_tile(), gate_flag=True))
    assert proven == _tile()
    assert "offset 24" in learner.provenance


def test_an_unflagged_press_is_not_believed_on_its_own():
    """Over Bluetooth there is no flag, so one press proves nothing."""
    learner = tl.TileLearner()
    assert learner.offer(_reading(_tile())) is None
    assert learner.needs_another_press


def test_two_bit_identical_presses_are_proof_without_any_flag():
    learner = tl.TileLearner()
    assert learner.offer(_reading(_tile())) is None
    proven = learner.offer(_reading(_tile()))
    assert proven == _tile()
    assert "bit-identical" in learner.provenance


def test_two_presses_that_differ_are_never_proof():
    """Genuine readings differ in the low bits -- 0.05 %R untouched spread."""
    learner = tl.TileLearner()
    a = _tile()
    b = list(a); b[5] += 0.02
    assert learner.offer(_reading(a)) is None
    assert learner.offer(_reading(b)) is None


def test_a_tile_looking_reading_is_not_self_certifying():
    """The guard must not learn from 'it looks like the tile' -- that is the
    question the guard exists to answer, and using it here would let the check
    validate itself."""
    learner = tl.TileLearner()
    assert learner.offer(_reading(TILE_SIGNATURE)) is None


# -- keying: one instrument never inherits another's constant ---------------

def test_each_unit_gets_its_own(store):
    tl.remember_signature(_tile(), "UNIT-A")
    tl.remember_signature(_tile(FOREIGN_GAP), "UNIT-B")
    assert tl.learned_signature("UNIT-A") == _tile()
    assert tl.learned_signature("UNIT-B") == _tile(FOREIGN_GAP)


def test_an_unlearned_unit_is_left_unarmed_not_given_someone_elses(store):
    tl.remember_signature(_tile(), "UNIT-A")
    assert tl.learned_signature("UNIT-B") is None


def test_an_unidentified_unit_is_armed_only_when_there_is_one(store):
    tl.remember_signature(_tile(), "UNIT-A")
    assert tl.learned_signature(None) == _tile()
    tl.remember_signature(_tile(FOREIGN_GAP), "UNIT-B")
    assert tl.learned_signature(None) is None


def test_forgetting_one_unit_leaves_the_other(store):
    tl.remember_signature(_tile(), "UNIT-A")
    tl.remember_signature(_tile(FOREIGN_GAP), "UNIT-B")
    tl.forget_signature("UNIT-B")
    assert tl.learned_signature("UNIT-B") is None
    assert tl.learned_signature("UNIT-A") == _tile()


def test_a_corrupt_store_disarms_rather_than_raising(store):
    store[tl.SIGNATURE_KEY] = "{not json"
    assert tl.learned_signature("UNIT-A") is None


def test_the_stored_precision_survives_the_round_trip(store):
    """The device returns 6 decimals; the built-in constant has 4, which is why
    it can never be matched bit-exactly. A learned value must keep all six."""
    six = [round(v + 0.000123, 6) for v in TILE_SIGNATURE]
    tl.remember_signature(six, "UNIT-A")
    assert tl.learned_signature("UNIT-A") == six
    assert json.loads(store[tl.SIGNATURE_KEY])["UNIT-A"] == six
