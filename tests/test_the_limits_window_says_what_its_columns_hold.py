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
    custom_iso_12647_7  16 limit-bearing rows
    custom_iso_12647_8  16 limit-bearing rows

The sixteen come from `compliance_sets._CUSTOM_PLACEHOLDER`, which is ChromIQ's
own figures chosen so that every measurable row has something to be judged
against. So the reader was told the empty columns were full, and that the full
ones carried a standard's numbers.

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
            path = (cs.resource_path(cs.ISO_DATA_FILE))
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
    # the Custom ones said to hold ChromIQ's own numbers.
    assert "empty here" in text, text
    assert "ChromIQ's own numbers rather than from theirs" in text, text


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
