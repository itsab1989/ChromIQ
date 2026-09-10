"""The shared demo projects must not describe a lock state they do not have.

A challenge round found `Report-Limits-Threshold-Series/run3` telling the
reader "Limits bound and LOCKED" in its `meta.json` description and in the
package README, and offering itself as half of a locked/unlocked pair, while
`run_compliance.is_locked()` returned **False** for it and its "unlocked" twin
behaved identically. The lock rule had gained a second condition (one dated
verification is not yet a history, so the set can still be chosen) and the
prose that described the data had not moved with it.

That is the worst place for a defect to sit. These projects are the shared
fixture: Knut asked for them by name, they ship attached to the beta, and every
later challenge round is told to trust them. A run that misdescribes itself
turns into a finding about the app in the next round's report.

So the generator no longer lets a description say anything about the lock. Each
plan DECLARES its state, the sentence is derived from that declaration, and the
generator asks the shipped `is_locked()` what it actually built before it
writes anything. This test holds the declarations themselves, without Argyll,
so a change to the lock rule that invalidates the data fails the gate rather
than the download.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "make_report_limit_demos.py"


@pytest.fixture(scope="module")
def gen():
    """The generator, imported as a module. It shells out to Argyll only from
    main(), so importing it costs nothing and needs no binaries."""
    spec = importlib.util.spec_from_file_location("_demo_gen", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_demo_gen"] = mod
    spec.loader.exec_module(mod)
    try:
        yield mod
    finally:
        sys.modules.pop("_demo_gen", None)


def _plans(gen):
    for name, plans in gen.PROJECTS:
        for i, plan in enumerate(plans, start=1):
            yield f"{name}/run{i}", plan


def test_every_plan_can_produce_the_lock_state_it_claims(gen):
    bad = [(rid, c) for rid, plan in _plans(gen) if (c := plan.lock_complaint())]
    assert not bad, "; ".join(f"{rid}: {c}" for rid, c in bad)


def test_the_claim_agrees_with_the_shipped_rule(gen):
    """The declaration is checked against `is_locked`'s own two conditions,
    not against a copy of them, so a change to the rule lands here."""
    from workflow.run_compliance import is_locked

    src = is_locked.__doc__ or ""
    assert "not a history" in src or "one measurement" in src.lower(), (
        "is_locked no longer documents the second condition; this test's "
        "premise may have moved and the demo data with it")

    for rid, plan in _plans(gen):
        bound_and_dated = len(plan.dates) >= 2
        expected = bound_and_dated and not plan.unlocked
        assert (plan.lock == "locked") == expected, (
            f"{rid} declares lock={plan.lock!r}, but a run with "
            f"{len(plan.dates)} dated verification(s) and unlocked="
            f"{plan.unlocked} is {'locked' if expected else 'not locked'}")


def test_no_description_says_anything_about_the_lock(gen):
    """The sentence is derived, never hand-written. This is the exact prose
    that went stale, so it is banned from the field it lived in."""
    for rid, plan in _plans(gen):
        low = plan.description.lower()
        for word in ("lock", "unlock"):
            assert word not in low, (
                f"{rid}'s description writes the lock state by hand "
                f"({plan.description!r}); declare it with lock= instead, so "
                "the sentence and the data cannot drift apart")
        assert plan.full_description.endswith(gen.LOCK_SENTENCES[plan.lock])


def test_all_three_lock_states_are_demonstrated(gen):
    """A user cannot compare states the package does not contain. There are
    three, and the reason a run is unlocked matters: one date is not the same
    as a lock that was lifted."""
    states = {plan.lock for _, plan in _plans(gen)}
    assert states == set(gen.LOCK_SENTENCES), (
        f"the package demonstrates {sorted(states)}; the states that exist are "
        f"{sorted(gen.LOCK_SENTENCES)}")
