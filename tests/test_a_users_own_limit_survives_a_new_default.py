"""A NUMBER THE USER SET IS NOT MOVED BY A NUMBER WE SHIP.

Knut's researched industry figures became the two Custom columns' starting
values on 2026-09-21 (#182). Ten of the thirty-six cells in those two columns
changed, so anybody who was already judging against a Custom column gets a
different verdict on the rows they left alone. That is the point of the
change. What must NOT happen is the other half: a limit that somebody typed in
themselves being replaced by one of ours.

The mechanism that protects them is real but indirect, and "it is applied on
top, so it wins" is the kind of reasoning that has been wrong here before. So
it is measured, in both places a user's own number can live:

* **A per-user override**, `{set_id: {row_id: number}}` in Preferences,
  applied over the factory table by `effective_limits`.
* **A per-run bound copy**, `meta.json::compliance_thresholds`, written once
  at a run's first verification and read back verbatim by `run_limits`.

**AND THE TEST IS PROVED NOT TO BE VACUOUS BEFORE IT IS BELIEVED.** A
before-and-after comparison over a population that cannot express the change
proves nothing at all, whatever colour it comes out: the round before this one
ran exactly such a diff over 3,564 cells, got "none moved", and the diff was
worthless because no measurement in it could have moved. So
`test_the_defaults_really_did_move_on_the_rows_this_is_proved_on` asserts the
movement FIRST, names the rows, and every other test here is driven on rows
taken from that list.

The "before" state is not a table of numbers retyped here. It is
`_CUSTOM_INDUSTRY` emptied, which is exactly what the two columns held until
2026-09-21: ChromIQ's own numbers on every measurable row. A second copy of
the old figures would be a second thing to keep right.

MUTATIONS PROVEN TO LAND (each run against this file, one at a time):
  * make `effective_limits` ignore its `overrides` argument for custom sets →
    `test_a_stored_override_survives_a_change_of_the_shipped_default` red.
  * make `run_limits` recompute from `effective_limits` for a bound run →
    `test_a_run_bound_before_the_change_keeps_the_numbers_it_was_bound_with`
    red.
  * put `_CUSTOM_INDUSTRY` back to `{}` (undo the whole change) →
    `test_the_defaults_really_did_move_on_the_rows_this_is_proved_on` red,
    and it is the first test in the file.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import workflow.compliance_sets as cs
from core.file_manager import Project
from workflow import run_compliance as rc
from workflow.compliance_sets import Limit, effective_limits, factory_limits

CUSTOM_SETS = ("custom_iso_12647_7", "custom_iso_12647_8")


@pytest.fixture
def before(monkeypatch):
    """Put the two Custom columns back to what they held before 2026-09-21.

    `_CUSTOM_INDUSTRY` emptied IS the old table: `custom_defaults` then
    returns `_CUSTOM_CHROMIQ_FILL` alone, which is the dict the columns used
    to share. Yielded as a callable so a test can step from one state to the
    other inside a single assertion.
    """
    def apply(old: bool) -> None:
        monkeypatch.setattr(cs, "_CUSTOM_INDUSTRY",
                            {} if old else _SHIPPED_INDUSTRY)
        cs.reset_iso_cache()
    yield apply
    cs.reset_iso_cache()


_SHIPPED_INDUSTRY = dict(cs._CUSTOM_INDUSTRY)


def _moved(set_id: str, before) -> "dict[str, tuple[Limit, Limit]]":
    """Every row of *set_id* whose factory limit changed, old against new."""
    before(True)
    old = factory_limits(set_id)
    before(False)
    new = factory_limits(set_id)
    return {rid: (old[rid], new[rid]) for rid in old
            if old[rid] != new.get(rid)}


# --------------------------------------------------- can it express anything?
def test_the_defaults_really_did_move_on_the_rows_this_is_proved_on(before):
    """FIRST, because every other test in this file is worthless without it.

    Both columns must have moved, on rows that carry a number in both states,
    or a guard saying "the user's value survived" is being driven over a
    change that did not happen.
    """
    total = 0
    for sid in CUSTOM_SETS:
        moved = _moved(sid, before)
        assert moved, (
            f"{sid}: not one limit changed when Knut's researched figures "
            "were applied. Every other test in this file would then be "
            "proving that a value survives a change that never came.")
        for rid, (old, new) in moved.items():
            assert old.is_numeric and new.is_numeric, rid
            assert cs.ROW_BY_ID[rid].status in ("now", "build", "ref"), rid
        total += len(moved)
    assert total >= 2


# ----------------------------------------------------------- the user's value
@pytest.mark.parametrize("set_id", CUSTOM_SETS)
def test_a_stored_override_survives_a_change_of_the_shipped_default(before, set_id):
    """The Preferences half, on a row whose default actually moved.

    The override is a third number, neither the old default nor the new one,
    so a test that "passed" by reading either table would be visible.
    """
    moved = _moved(set_id, before)
    rid, (old, new) = sorted(moved.items())[0]
    mine = round(float(old.number) + float(new.number) + 0.37, 3)
    overrides = {set_id: {rid: mine}}

    before(True)
    assert effective_limits(set_id, overrides)[rid] == Limit.value(mine)

    before(False)
    got = effective_limits(set_id, overrides)[rid]
    assert got == Limit.value(mine), (
        f"{rid}: the user set {mine} and the new shipped default {new.number} "
        f"took its place. A limit somebody typed in is not ours to move.")

    # …and the SAME column, on a row the user left alone, DID take the new
    # number. Without this the test above passes on a column that changed
    # nothing.
    untouched = sorted(r for r in moved if r != rid)
    if untouched:
        other = untouched[0]
        assert effective_limits(set_id, overrides)[other] == moved[other][1]
        assert effective_limits(set_id, overrides)[other] != moved[other][0]


@pytest.mark.parametrize("set_id", CUSTOM_SETS)
def test_an_override_on_a_row_that_did_not_move_is_also_untouched(before, set_id):
    """The quieter half: a Custom column is editable on EVERY row, and most
    rows did not move. A user's number on one of those must be just as safe,
    or the guard above is only testing the rows we happened to change."""
    moved = _moved(set_id, before)
    still = sorted(r for r in factory_limits(set_id) if r not in moved
                   and factory_limits(set_id)[r].is_numeric)
    assert still, "every row moved; this test is measuring the wrong thing"
    rid = still[0]
    overrides = {set_id: {rid: 7.25}}
    before(True)
    assert effective_limits(set_id, overrides)[rid] == Limit.value(7.25)
    before(False)
    assert effective_limits(set_id, overrides)[rid] == Limit.value(7.25)


@pytest.mark.parametrize("set_id", CUSTOM_SETS)
def test_a_users_no_limit_survives_too(before, set_id):
    """"–" is a decision as much as a number is.

    A user who turned a spin box down to 0 said "do not judge this row". A new
    default must not put a limit back on it, which is the same rule stated for
    the one override whose value is not a number.
    """
    moved = _moved(set_id, before)
    rid = sorted(moved)[0]
    overrides = {set_id: {rid: None}}
    before(True)
    assert effective_limits(set_id, overrides)[rid] == Limit.none()
    before(False)
    assert effective_limits(set_id, overrides)[rid] == Limit.none(), (
        f"{rid}: the user removed this limit and a new default put one back")


# ------------------------------------------------------------ the run's copy
def _project(tmp_path: Path):
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    return proj, run


@pytest.mark.parametrize("set_id", CUSTOM_SETS)
def test_a_run_bound_before_the_change_keeps_the_numbers_it_was_bound_with(
        before, tmp_path, set_id):
    """The per-run half, which is where a judged verdict actually comes from.

    A run bound while the old defaults shipped carries its own copy of them.
    Reading it back after the new defaults arrive must give the OLD numbers on
    every row, including the ones we changed: a dated verification saved last
    month is judged with the column it was judged with last month, or the
    report's history stops meaning anything.
    """
    moved = _moved(set_id, before)
    before(True)
    _proj, run = _project(tmp_path / set_id)
    bound = rc.bind_run(run, set_id, {})
    assert bound.bound
    was = dict(bound.limits)

    before(False)
    now = rc.run_limits(run, {})
    assert now.bound and now.set_id == set_id
    for rid, (old, _new) in moved.items():
        assert now.limits[rid] == old, (
            f"{rid}: a run bound to {set_id} was re-judged with the new "
            f"shipped default. Its stored copy said {old.number}.")
    assert now.limits == was
    # …and ChromIQ says so rather than hiding it: the stored copy now differs
    # from the set, which is exactly what "edited" is derived from.
    assert now.edited


@pytest.mark.parametrize("set_id", CUSTOM_SETS)
def test_a_run_bound_after_the_change_gets_the_new_numbers(before, tmp_path, set_id):
    """The other direction, and the reason the change was asked for.

    Nothing has been "kept safe" if a run bound today still gets last month's
    numbers. New defaults apply where nothing has been set.
    """
    moved = _moved(set_id, before)
    before(False)
    _proj, run = _project(tmp_path / set_id)
    bound = rc.bind_run(run, set_id, {})
    for rid, (_old, new) in moved.items():
        assert bound.limits[rid] == new, rid
    assert not bound.edited
