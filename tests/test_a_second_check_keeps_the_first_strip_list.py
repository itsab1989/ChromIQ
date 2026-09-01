"""A check must never destroy the previous check's strip list.

`write_refine_strips` wrote one fixed name and overwrote it in place, so a
second check took the first one's list away without a word — against the
project's absolute rule that nothing the user created is deleted, only
archived. Its sibling `write_quality_report` had numbered its files all along.
Proved by a challenge round, which hand-edited the file and watched the next
check remove it (2026-09-01).
"""
import pathlib

from workflow.profcheck_runner import parse_refine_strips, write_refine_strips


def test_a_second_check_does_not_take_the_first_list_away(tmp_path):
    first = write_refine_strips(tmp_path, "Chart", [("A", 3.0), ("B", 4.0)])
    first.write_text(first.read_text() + "# a note the user added\n")

    second = write_refine_strips(tmp_path, "Chart", [("C", 5.0)])

    assert second != first, "the second check wrote over the first one's list"
    assert first.exists(), "the first list was destroyed"
    assert "a note the user added" in first.read_text(), (
        "the first list survived in name only")
    assert parse_refine_strips(second) == ["C"]
    assert parse_refine_strips(first) == ["A", "B"]


def test_the_numbering_climbs(tmp_path):
    names = [write_refine_strips(tmp_path, "Chart", [("A", 1.0)]).name
             for _ in range(3)]
    assert len(set(names)) == 3, f"names repeated: {names}"
    assert names[0].startswith("Refine_Strips_1_")


def test_an_older_unnumbered_file_is_left_alone(tmp_path):
    """A file written by an earlier version is the user's; it is not renamed."""
    old = tmp_path / "Refine_Strips_Chart.txt"
    old.write_text("# CHROMIQ_REFINE_STRIPS_V1\n# Strip\tMaxDE\nZ\t9.00\n")
    write_refine_strips(tmp_path, "Chart", [("A", 1.0)])
    assert old.exists() and parse_refine_strips(old) == ["Z"], (
        "a strip list from an older version was moved or overwritten")
