"""The shared demo projects must not describe a limit state they do not have.

**K31 (beta 40):** there is no lock left to describe; see the note above the
first test. The file keeps its name so its history can be found.

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


# K31 (Knut, #182 5801677743, beta 40): the run lock, "Unlock this run's
# limits" and the binding of a run to a set are gone, so the three lock
# states this file used to hold the demo data to are gone with them. What
# stays is the rule the file was written for: the demo projects never
# describe a limit state by hand, the sentence is derived, and the README's
# index names runs from measured rows.
def test_no_description_says_anything_about_a_lock(gen):
    """MUTATION: write "locked" or "bound to" into a plan's description, or
    drop the derived sentence from `full_description`, and this goes red."""
    for rid, plan in _plans(gen):
        low = plan.description.lower()
        for word in ("lock", "unlock", "bound to"):
            assert word not in low, (
                f"{rid}'s description writes a limit state by hand "
                f"({plan.description!r})")
        assert plan.full_description.endswith(
            gen.LIMIT_SENTENCE.format(set=plan.set_name))


def test_the_limit_sentence_names_the_set_and_no_lock(gen):
    """The one sentence names the set (Knut, 2026-09-11: a sentence about
    limits must say which set) and says nothing about a lock, a binding or a
    correction.

    MUTATION: drop "{set}" from `LIMIT_SENTENCE`, or put "bound" or "locked"
    back into it, and this goes red."""
    s = gen.LIMIT_SENTENCE
    assert "{set}" in s
    for word in ("lock", "bound", "never", "lifted"):
        assert word not in s.lower(), (word, s)
    for rid, plan in _plans(gen):
        text = plan.full_description
        assert "{" not in text, f"{rid}'s description has an unfilled slot"
        assert plan.set_name.split(",")[0] in text, (
            f"{rid}'s description does not name its limit set")


def test_no_plan_declares_a_lock_state_any_more(gen):
    """MUTATION: put `lock` or `unlocked` back on `RunPlan` and this goes
    red."""
    import dataclasses
    names = {f.name for f in dataclasses.fields(gen.RunPlan)}
    assert not names & {"lock", "unlocked"}, names
    assert not hasattr(gen, "LOCK_SENTENCES")


def test_the_readme_never_writes_a_lock_claim(gen):
    """The README's own source may not spell a lock claim at all since K31:
    there is no lock left for one to describe.

    MUTATION: put the "WHICH RUNS ARE LOCKED, AND WHY" section back and this
    goes red."""
    import inspect
    import re

    src = inspect.getsource(gen.readme)
    literals = re.findall(r'a\(\s*(?:f?)"((?:[^"\\]|\\.)*)"', src)
    assert literals, "readme() no longer writes string literals; this test is blind"
    offenders = [t for t in literals
                 if re.search(r"\b(un)?lock(ed)?\b|Unlock this run", t, re.I)]
    assert not offenders, "; ".join(repr(t) for t in offenders)


def test_the_index_names_a_run_whose_new_reports_start_on_its_own_set(gen):
    """The index answers from measured rows (K31: a run's own default for
    new reports, read back with `run_limits`)."""
    rows = [{"run": "Threshold-Series/run1", "dates": 11,
             "starts_on": "chromiq_default"},
            {"run": "Set-Compare/run2", "dates": 1,
             "starts_on": "chromiq_tight"}]
    got = dict(gen._lock_index(rows))
    assert got == {"new reports start on a set of its own":
                   "Set-Compare, run2"}, got


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


# ---------------------------------------------------------------------------
# The other number the README used to get wrong
# ---------------------------------------------------------------------------
def _sheet(p: Path, n: int) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"CTI2\n\nNUMBER_OF_SETS {n}\nBEGIN_DATA\nEND_DATA\n",
                 encoding="utf-8")


def test_the_readme_names_the_count_the_report_will_show(gen, tmp_path):
    """TWO COUNTS, AND THE README PRINTED THE ONE NOBODY EVER SEES.

    `printtarg` pads a sheet to fill its rows. The 156-patch A3 verification
    chart goes on paper as 168 and the 400-patch profile chart as 405, and
    those extra patches are printtarg's own: they are not in the `.ti1`, so
    nothing measures them and no report counts them.

    The README read the `.ti2` and printed 168. The reader opens the report
    beside it to match one against the other, and the report says 156.
    Measured across the built package: 31 dated reports, three of them padded,
    all three disagreeing with the file that describes them.

    So the number in front is the measured one, taken from the `.ti3`, and the
    sheet's own count is named after it because that is what a reader counts if
    they hold the print.

    MUTATION: read the count off the `.ti2` again and this goes red.
    """
    dest = tmp_path / "D"
    run = dest / "P" / "runs" / "run1"
    _sheet(run / "chart.ti2", 405)
    _sheet(run / "chart.ti3", 400)
    _sheet(run / "verifications" / "v.ti2", 168)
    _sheet(run / "verifications" / "2026-01-01_100000" / "v.ti3", 156)

    profile = gen._chart_label(dest, "P", "run1", gen.CHART_LARGE)
    verify = gen._chart_label(dest, "P", "run1", gen.CHART_WIDE, True)

    assert profile.startswith("400 patches"), profile
    assert "405" in profile and "not measured and not judged" in profile, profile
    assert verify.startswith("156 patches"), verify
    assert "168" in verify and "not measured and not judged" in verify, verify


def test_a_chart_that_was_not_padded_says_nothing_extra(gen, tmp_path):
    """The nine runs printtarg left alone must not gain a parenthesis.

    MUTATION: append the note unconditionally and this goes red.
    """
    dest = tmp_path / "D"
    run = dest / "P" / "runs" / "run1"
    _sheet(run / "chart.ti2", 210)
    _sheet(run / "chart.ti3", 210)
    assert gen._chart_label(dest, "P", "run1", gen.CHART_MEDIUM) == \
        gen.CHART_MEDIUM.label


def test_measurements_that_disagree_are_reported_not_picked_between(gen,
                                                                    tmp_path):
    """Three dates, three different patch counts, and no honest single number.

    Saying one of them would be a guess presented as a reading, which is the
    fault this whole function exists to have stopped.
    """
    dest = tmp_path / "D"
    v = dest / "P" / "runs" / "run1" / "verifications"
    _sheet(v / "v.ti2", 168)
    _sheet(v / "2026-01-01_100000" / "v.ti3", 156)
    _sheet(v / "2026-02-01_100000" / "v.ti3", 150)

    label = gen._chart_label(dest, "P", "run1", gen.CHART_WIDE, True)
    assert "disagree" in label and "150" in label and "156" in label, label
