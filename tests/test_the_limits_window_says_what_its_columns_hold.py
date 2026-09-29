"""The Report limits window's own description of its columns is MEASURED.

B8-571. The masthead tooltip of `ui/dialogs/thresholds_dialog.py` said, in one
sentence and unconditionally:

    "The two ISO columns hold a standard's published values and are read-only;
     the two Custom columns start from them and are yours to change."

Both clauses are false of a ChromIQ as it ships. Measured against the
repository's own `data/compliance_sets/iso12647.json`, which is deliberately
empty:

    iso_12647_7          0 limit-bearing rows
    iso_12647_8          0 limit-bearing rows
    custom_iso_12647_7  18 limit-bearing rows
    custom_iso_12647_8  18 limit-bearing rows

Not one of those eighteen is a standard's figure. They come from
`compliance_sets.custom_defaults`, which merges Knut's researched industry
figures (#182, 2026-09-21) over ChromIQ's own numbers so that every measurable
row has something to be judged against. So the reader was told the empty
columns were full, and that the full ones carried a standard's numbers.

**This is the fourth time this exact claim has had to be removed.** The `SetDef`
blurbs were corrected for it three times and the report guide's own paragraph
once; each correction was made where it was noticed and this copy, twenty lines
above the conditional that guards the blurbs, was never revisited.

So the guard does not pin words. It **counts the limits the window is actually
drawing** and requires the paragraph to match, in both states: with the shipped
empty file, and with a file that supplies figures. A sentence that stops being
true of what the table holds fails here whatever it says.

MUTATION PROVEN TO LAND: make `_columns_paragraph` return its `supplied` branch
unconditionally and `test_the_shipping_state_is_not_described_as_full` goes red;
return the shipping branch unconditionally and
`test_supplied_values_are_not_described_as_absent` goes red.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import compliance_sets as cs                        # noqa: E402
from ui.dialogs.thresholds_dialog import _columns_paragraph       # noqa: E402

ISO_SETS = ("iso_12647_7", "iso_12647_8")
CUSTOM_SETS = ("custom_iso_12647_7", "custom_iso_12647_8")


@pytest.fixture
def iso_file(tmp_path, monkeypatch):
    """Point ChromIQ at a values file of this test's own making.

    THE ENVIRONMENT VARIABLE IS THE ONLY SAFE HANDLE HERE. `_iso_data_path`
    prefers the USER'S OWN file at `~/Library/Preferences/ChromIQ/compliance/`
    over the repository's, so on a developer machine that holds a licence
    holder's real figures this suite would otherwise measure those. It also
    means a test must never assert a particular number; it counts rows.
    """
    def use(payload: "dict | None"):
        path = tmp_path / "iso12647.json"
        if payload is None:
            # THE EMPTY SHIPPED STATE, BY FIXTURE. This used to read the
            # repository's own file, which was empty by design; since #182
            # S-2 (§23) that file may ship a set, so the empty state is stood
            # in for the shipped file here and stays measurable either way.
            path = tmp_path / "shipped-empty-iso12647.json"
            path.write_text(json.dumps({"iso_12647_7": {}, "iso_12647_8": {}}),
                            encoding="utf-8")
            monkeypatch.setattr(cs, "_bundled_iso_path", lambda: path)
        else:
            path.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setenv(cs.ISO_DATA_ENV, str(path))
        cs.reset_iso_cache()
        return path
    yield use
    cs.reset_iso_cache()


def _judged(set_id: str) -> int:
    return len(cs.limit_bearing(cs.factory_limits(set_id)))


# ---------------------------------------------------------------- the facts
def test_the_shipped_file_really_is_empty_and_the_custom_sets_really_are_not():
    """The measurement the paragraph has to agree with, taken first.

    If this ever changes -- ChromIQ gains permission to ship the figures, or
    the Custom placeholders go -- the tests below are measuring a different
    world and should be read again rather than patched.
    """
    payload = json.loads(
        cs.resource_path(cs.ISO_DATA_FILE).read_text(encoding="utf-8"))
    # #182 S-2, §23: the file may now ship a set, complete. The tests below
    # that use `iso_file(None)` measure the EMPTY state, which is what the
    # repository holds until the owner's go-ahead; once a set ships they
    # measure a different world, and this is where that is noticed first.
    # The shipped state is measured in `test_iso_values_ship_as_values_only`.
    if payload.get("iso_12647_7") or payload.get("iso_12647_8"):
        pytest.skip("a set ships; the empty state is measured by fixture")
    assert payload.get("iso_12647_7") == {}
    assert payload.get("iso_12647_8") == {}


def test_the_shipping_state_is_not_described_as_full(iso_file):
    iso_file(None)
    assert [_judged(s) for s in ISO_SETS] == [0, 0], \
        "the shipped ISO columns judge nothing; this test is measuring something else"
    assert all(_judged(s) > 0 for s in CUSTOM_SETS)

    text = _columns_paragraph()
    # THE FALSE SENTENCE ITSELF, in every spelling it has had.
    assert "start from them" not in text, text
    for bad in ("The two ISO columns hold a standard's published values",
                "the two Custom columns start from them"):
        assert bad not in text, text
    # …and what has to be there instead: the ISO columns said to be empty, and
    # the Custom ones said to hold NO published value of either standard.
    assert "empty here" in text, text
    assert "hold none of their published values" in text, text


def test_the_paragraph_names_every_source_the_custom_columns_draw_on(iso_file):
    """A source with limits behind it is NAMED; one without is not.

    Knut's researched industry figures became the Custom columns' starting
    values on 2026-09-21 (#182). A column named after a standard that holds
    numbers which are not that standard's has to say where they came from, and
    a sentence that names one of two sources is as wrong as one that names a
    standard: eight of Custom ISO 12647-7's eighteen limits, and nine of
    Custom ISO 12647-8's, are still ChromIQ's own.

    Phrased as the implication rather than as fixed wording, and driven in
    three states, so the sentence is pinned to what the module actually holds.

    MUTATION PROVEN TO LAND: empty `_CUSTOM_INDUSTRY` and the "industry
    practice" clause disappears with the count, so the *seen* half of each
    assertion moves with the *counted* half and the test stays green -- which
    is why the count is also asserted to be non-zero as shipped, below.
    Hard-code the sentence to always name industry practice, and the
    `_CUSTOM_INDUSTRY = {}` leg goes red.
    """
    from ui.dialogs.thresholds_dialog import _custom_columns_sentence

    for payload in (None,
                    {"iso_12647_7": {"all_de00_avg": 1.0}},
                    {"iso_12647_7": {"all_de00_avg": 1.0},
                     "iso_12647_8": {"all_de00_avg": 1.0}}):
        iso_file(payload)
        totals = {"supplied": 0, "industry": 0, "chromiq": 0}
        for sid in CUSTOM_SETS:
            counts = cs.custom_default_counts(sid)
            for key in totals:
                totals[key] += counts[key]
        text = _custom_columns_sentence()
        for key, phrase in (("supplied", "the figures you supplied"),
                            ("industry",
                             "limits researched from industry practice"),
                            ("chromiq", "ChromIQ's own numbers")):
            assert (phrase in text) == bool(totals[key]), (
                f"{key}: {totals[key]} limits behind it, and the window "
                f"{'names' if phrase in text else 'does not name'} it -- {text}")


def test_the_industry_research_is_actually_behind_the_custom_columns(iso_file):
    """The half the test above cannot prove on its own.

    That test says "named when counted", which an empty `_CUSTOM_INDUSTRY`
    satisfies vacuously. This one says the count is not zero as ChromIQ ships:
    Knut asked for his researched figures to be the starting values of BOTH
    Custom columns, so both must draw on them.
    """
    iso_file(None)
    for sid in CUSTOM_SETS:
        counts = cs.custom_default_counts(sid)
        assert counts["industry"] > 0, (
            f"{sid} starts from no researched figure at all; Knut asked for "
            f"them to be its defaults (#182, 2026-09-21)")
        assert counts["supplied"] == 0, (
            f"{sid} took a figure from a values file; the repository's own "
            f"file is empty, so this test is measuring the wrong machine")


def test_supplied_values_are_not_described_as_absent(iso_file):
    """The other state, and the one the old sentence was written for.

    A number on ONE measurable row of one ISO set is enough to make that column
    non-empty, so the paragraph must stop saying it is empty. No real figure is
    used: 1.0 on the all-patch average is ChromIQ's arithmetic, not anybody's
    standard.
    """
    iso_file({"iso_12647_7": {"all_de00_avg": 1.0},
              "iso_12647_8": {"all_de00_avg": 1.0}})
    assert all(_judged(s) > 0 for s in ISO_SETS)

    text = _columns_paragraph()
    assert "empty here" not in text, text
    assert "you supplied from your own copy" in text, text
    # and it must not claim ChromIQ shipped them
    assert "ChromIQ has no permission to include" not in text, text


# ------------------------------------------------- the rule behind the words
@pytest.mark.parametrize("supplied", [False, True])
def test_the_paragraph_never_says_a_column_holds_what_it_does_not(iso_file, supplied):
    """The drift guard: emptiness is a COUNT, and the sentence follows it.

    Whatever wording this paragraph grows, it may not say an ISO column is
    empty while that column judges rows, nor imply it is filled while it judges
    none. Phrased as the two implications rather than as fixed strings, so a
    rewrite that stays honest passes and one that does not cannot.
    """
    iso_file({"iso_12647_7": {"all_de00_avg": 1.0}} if supplied else None)
    empty = not any(_judged(s) for s in ISO_SETS)
    text = _columns_paragraph()
    says_empty = "empty here" in text
    assert says_empty == empty, (
        f"the ISO columns judge "
        f"{[_judged(s) for s in ISO_SETS]} rows and the window says "
        f"{'they are empty' if says_empty else 'nothing about being empty'}")


def test_the_custom_columns_are_never_called_a_standards_figures(iso_file):
    """Whichever state, a Custom column is the user's to change and is not a
    standard speaking. The promise made to a rights holder is that ChromIQ
    never presents its own numbers as theirs."""
    for payload in (None, {"iso_12647_7": {"all_de00_avg": 1.0}}):
        iso_file(payload)
        text = _columns_paragraph()
        assert "yours to change" in text, text
