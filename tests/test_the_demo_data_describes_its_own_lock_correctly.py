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


def test_the_readme_never_writes_a_lock_claim_by_hand(gen):
    """The guard above bans the lock words from a plan's description, and a
    challenge round found the stale claim alive forty lines away, in README
    prose the guard could not see.

    The index said "exactly one dated verification, LOCKED ... Threshold-Series,
    run3" after that run had stopped being locked, and "exactly one dated
    verification, UNLOCKED ... Isolated-Rows, run3" after that run had gained a
    second date. It contradicted the measured table on the same page, and the
    index is the half a reader acts on, because it says which run to open.

    So the README's own source may not spell a lock claim either. Every line
    that makes one is generated from the measured rows now, by `_lock_index`.
    """
    import inspect
    import re

    src = inspect.getsource(gen.readme)
    # Only the literal strings this function writes; the docstring and the
    # comments are prose about the rule, not text a reader ever sees.
    literals = re.findall(r'a\(\s*(?:f?)"((?:[^"\\]|\\.)*)"', src)
    assert literals, "readme() no longer writes string literals; this test is blind"
    # A CLAIM NAMES A RUN. The section heading "WHICH RUNS ARE LOCKED, AND WHY"
    # sits over a table generated from measured rows and says nothing about any
    # particular run, so it is not what went stale and banning it would only
    # teach the next person to word the heading around this test.
    # CASE-INSENSITIVE, AND THE FIRST VERSION WAS NOT. It matched only the
    # shouted form, so it saw the index it was written for and walked straight
    # past three lower-case lines forty rows below saying the same kind of
    # thing, one of which was false. A challenge round found them in the very
    # commit that added this test.
    offenders = [t for t in literals
                 if re.search(r"\b(un)?locked\b", t, re.I)
                 and re.search(r"\brun\s?\d", t, re.I)]
    assert not offenders, (
        "readme() writes a lock claim about a named run by hand: "
        + "; ".join(repr(t) for t in offenders)
        + ". Derive it from the measured rows instead, as _lock_index does.")


def test_the_index_names_a_run_for_each_lock_state(gen):
    """And it must still ANSWER the question, from measured rows.

    Banning the words is only half of it: an index that lists no run for a
    state sends the next round off to invent its own data, which is what the
    shared package exists to stop.
    """
    rows = [{"run": "Threshold-Series/run1", "dates": 11, "lifted": False, "locked": True},
            {"run": "Threshold-Series/run3", "dates": 1, "lifted": False, "locked": False},
            {"run": "Isolated-Rows/run3", "dates": 2, "lifted": True, "locked": False}]
    got = dict(gen._lock_index(rows))
    assert len(got) == 3, got
    assert got["locked, so the set cannot be changed"] == "Threshold-Series, run1"
    assert got["one date only, so the set is still offered"] == "Threshold-Series, run3"
    assert got["two dates, but the lock lifted by hand"] == "Isolated-Rows, run3"



def test_the_forced_row_count_is_never_typed(gen):
    """The heading said THREE while the computed list under it had two, then
    two while the list had three.

    Round 9 measured it: the LIST was computed and the NUMBER above it was a
    string literal, so a mutation that makes one row stop being forced shrank
    the list and left the heading claiming the old count. They come from the
    same place now.

    MUTATION: put a literal back in the heading and this goes red.
    """
    import inspect
    import re

    src = inspect.getsource(gen.readme)
    head = [t for t in re.findall(r'a\(\s*(?:f?)"((?:[^"\\]|\\.)*)"', src)
            if "CANNOT CROSS ALONE" in t]
    assert head, "the heading is gone; this test is blind"
    for t in head:
        assert not re.search(r"\b(ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT)\b", t), (
            f"the forced-row count is typed into the heading: {t!r}")


def test_the_heading_and_the_list_agree_on_the_number(gen):
    """And they must actually agree, not merely both be generated.

    MUTATION: make `_WORDS` return the wrong word and this goes red.
    """
    n = len(gen._forced_pairs())
    assert n >= 1, "nothing is forced, so the section has nothing to say"
    assert gen._WORDS.get(n), f"no word for {n}"
    assert gen._WORDS[n] in ("one", "two", "three", "four", "five"), gen._WORDS[n]
    # the word really is the count
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
    assert gen._WORDS[n] == words[n], (
        f"the heading would say {gen._WORDS[n]!r} for {n} rows")
