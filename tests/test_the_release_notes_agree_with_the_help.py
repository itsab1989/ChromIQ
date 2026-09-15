"""The release notes may not re-assert a claim the same entry says was wrong.

`CHANGELOG.md`'s top entry is not an internal document: `build-release.yml`,
`build-windows.yml` and `build-linux.yml` all pull it out by tag with

    awk "/^## ${TAG}$/{found=1; next} found && /^## /{exit} found{print}"

and post it as the GitHub Release body, so it is the first thing a tester reads
about a build.

The v4.3.0-beta.17 entry said both of these, the second one later and therefore
last:

* Fixed: *"an ordinary test chart does not simply read N-A on the paper and
  solid rows, because a ChromIQ set puts no limit on them and they are dropped
  from the table instead"*
* Changed: *"An ordinary test chart has no aim values, and those rows read
  N-A."*

The shipped help text carries the corrected version, so the notes also
misdescribed the change they were announcing.

MEASURED ON SCREEN, 2026-09-15, in the real Measurement Report window on a
project with five dated verifications
(`scripts/adv23d_the_report_help_in_three_languages.py`): Full colour check on
ChromIQ default lists seven rows, and `substrate_de00_max` and
`solids_de00_max` are not among them; the note under the results names only the
two grey rows. `compliance_sets.row_verdict` is why, in one line: a limit of
kind ``none`` returns ``INFO if value is not None else None``, and an ordinary
chart supplies no value for those rows, so there is no row at all. Under a
Custom ISO set the same rows carry a number, so a missing value reads N-A.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]


def _top_entry() -> str:
    """Exactly what the release workflows would post, for the newest tag."""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    parts = re.split(r"(?m)^## ", text)
    assert len(parts) > 1, "CHANGELOG.md has no version headings"
    return parts[1]


def test_the_changelog_does_not_contradict_the_help_it_describes():
    """MUTATION: put "those rows read N-A" back and this goes red."""
    entry = " ".join(_top_entry().split())
    assert "those rows read N-A" not in entry, (
        "the release notes say an ordinary test chart makes the paper and "
        "solid rows read N-A. Measured in the window, a ChromIQ set drops "
        "them from the table instead, and the same entry's Fixed section "
        "already says so")
    # …and it must say what really happens, not merely stop saying the wrong
    # thing. Both halves, because the answer depends on the set.
    assert "left out of the table" in entry, entry[-1200:]
    assert "Custom ISO set shows them as N-A" in entry, entry[-1200:]


def test_the_help_says_a_chromiq_set_drops_those_rows_rather_than_n_a():
    """The sentence the notes are supposed to be describing."""
    from ui.dialogs.measurement_report_dialog import _CHART_HELP
    help_text = " ".join(_CHART_HELP.split())
    assert ("a ChromIQ set puts no limit on those rows anyway, so they are "
            "left out of the table altogether") in help_text, help_text
    assert "a Custom ISO set shows them as N-A" in help_text, help_text


def test_a_row_with_no_limit_and_no_value_is_not_a_row_at_all():
    """The one line the whole claim rests on, so nobody has to re-derive it."""
    from workflow.compliance_sets import INFO, N_A, Limit, row_verdict
    assert row_verdict(Limit.none(), None, True) is None, (
        "a row with no limit and no value would be shown, so 'left out of the "
        "table altogether' would be false")
    assert row_verdict(Limit.none(), 1.2, True) == INFO
    assert row_verdict(Limit.value(3.0), None, True) == N_A, (
        "a Custom ISO set's row with no value would not read N-A")
