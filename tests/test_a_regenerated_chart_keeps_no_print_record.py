"""A regenerated chart must not inherit the old chart's print record.

`<stem>.print.json` says how THIS sheet was produced: through the profile or
raw, which intent, which profile file, which route. `Run.chart_artefact_names()`
and the wipe list in `Run.reset_chart_artefacts` both left it out, so pressing
Generate Chart replaced every chart file and kept the record - and the record
then belonged to a sheet that no longer existed.

That is not a cosmetic leftover. `workflow/measurement_report.py` reads the
record and, when it says "through the profile" with a white-mapping intent,
switches the whole report from an ABSOLUTE yardstick to a MEDIA-RELATIVE one.
Every ΔE00 in the report moves. So a stale record does not merely state a
provenance that never happened; it silently re-scales the numbers the user
judges the profile by.

The give-away had been in the file for as long as the sidecar had: the comment
at `Calibration.chart_files` names this exact list and this exact omission
("`.strips.json` and `.print.json` have both been forgotten by such a list
already (`Run.chart_artefact_names`)"), two hundred lines above the list that
still had the hole.
"""
from __future__ import annotations

import json
from pathlib import Path

from core.file_manager import Project
from workflow.verification_print import (print_record_path, read_print_record,
                                         write_print_record)


def _chart(run, text: str) -> None:
    """Everything a generated chart puts at the run root."""
    run.ensure_dir()
    for p in (run.chart_ti1, run.chart_ti2, run.chart_cht, run.chart_ps,
              run.chart_channels_json):
        p.write_text(text, encoding="utf-8")
    (run.dir / f"{run.stem}.strips.json").write_text(text, encoding="utf-8")


def _print_it(run, *, colour="through-profile", intent="relative"):
    prof = run.dir / "old-profile.icc"
    prof.write_bytes(b"icc")
    return write_print_record(run.chart_ti2, colour=colour, intent=intent,
                              profile=prof, route="chromiq")


# ---------------------------------------------------------------------------
# The list, and the wipe that uses it
# ---------------------------------------------------------------------------

def test_the_print_record_is_named_as_a_chart_artefact(tmp_path):
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    assert f"{run.stem}.print.json" in run.chart_artefact_names()


def test_regenerating_a_chart_takes_the_print_record_with_it(tmp_path):
    """The real build path: `reset_chart_artefacts()` is what Generate Chart
    calls before it writes anything."""
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    _chart(run, "the chart that was printed")
    rec = _print_it(run)
    assert rec is not None and rec.exists()
    assert read_print_record(run.measurement_ti3) is not None

    run.reset_chart_artefacts()               # <- Generate Chart, first act

    assert not print_record_path(run.chart_ti2).exists(), (
        "the regenerate kept the OLD chart's print record; the next "
        "measurement report will state a provenance that never happened")
    assert not run.chart_ti2.exists()         # the chart itself did go


def test_a_stashed_regenerate_sets_the_record_aside_with_the_chart(tmp_path):
    """`stash=True` is the branch that can put a chart BACK. The record has to
    travel with it, or Restore Used Chart returns a chart whose provenance was
    thrown away."""
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    _chart(run, "chart one")
    _print_it(run)

    stash = run.reset_chart_artefacts(stash=True)

    assert stash is not None
    assert (stash / f"{run.stem}.print.json").is_file(), (
        "the print record was deleted instead of being set aside, so the "
        "chart can come back and its record cannot")


def test_the_record_is_not_taken_when_the_chart_is_kept(tmp_path):
    """Restore Used Chart redraws the pages of the chart that is already
    there (`keep_results=True`). Nothing about how it was printed changes, so
    the record must survive."""
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    _chart(run, "chart one")
    _print_it(run)
    run.measurement_ti3.write_text("m", encoding="utf-8")

    run.reset_chart_artefacts(keep_results=True)

    # keep_results keeps the measurement; the chart files (record included) are
    # replaced by the redraw, which is what the caller asked for.
    assert run.measurement_ti3.exists()


# ---------------------------------------------------------------------------
# What the report actually says, before and after
# ---------------------------------------------------------------------------

def test_the_reports_provenance_changes_when_the_record_goes(tmp_path):
    """Read through the report's own reader, on the report's own path.

    Before the fix this asserted the same value twice: the record survived the
    regenerate, so the new chart answered with the old chart's provenance.
    """
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    _chart(run, "chart one")
    _print_it(run, colour="through-profile", intent="relative")

    before = read_print_record(run.measurement_ti3)
    assert before is not None
    assert before["colour"] == "through-profile"
    assert before["intent"] == "relative"

    run.reset_chart_artefacts()
    _chart(run, "chart two - a different chart entirely")

    after = read_print_record(run.measurement_ti3)
    assert after is None, (
        "the new chart is answering with the old chart's print record: the "
        f"report would state {after!r} for a sheet printed no such way")


def test_a_stale_record_would_have_moved_the_reports_yardstick(tmp_path):
    """Why this is worth a test at all.

    The report does not merely print the record. A record saying "through the
    profile" with a white-mapping intent switches the yardstick to
    media-relative, and every ΔE00 in the report is then measured against the
    paper's white instead of L*=100. This pins the rule the report applies, so
    the cost of a stale record is on the record rather than in a memory.
    """
    import inspect

    import workflow.measurement_report as mr
    src = inspect.getsource(mr.build_report)
    assert 'report["yardstick"] = "media-relative"' in src
    assert "printing" in src

    # …and the condition really is the record's own two fields.
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    _chart(run, "c")
    _print_it(run, colour="through-profile", intent="relative")
    rec = json.loads(print_record_path(run.chart_ti2).read_text(encoding="utf-8"))
    assert rec["colour"] == "through-profile" and rec["intent"] == "relative"


# ---------------------------------------------------------------------------
# The rest of the family
# ---------------------------------------------------------------------------

def test_every_per_chart_sidecar_is_on_both_lists(tmp_path):
    """The hole was one name in two lists, and the way to keep it shut is to
    ask what the family IS rather than to remember its members.

    Three sidecars are written beside a chart under the chart's own stem:
    `.channels.json` (how many inks and in what order), `.strips.json` (where
    the strips are on the sheet) and `.print.json` (how the sheet was
    printed). All three describe THAT chart, so all three go when it goes.
    """
    import inspect

    from core.file_manager import Run
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    names = run.chart_artefact_names()
    wipe = inspect.getsource(Run.reset_chart_artefacts)
    for sidecar in (".channels.json", ".strips.json", ".print.json"):
        assert f"{run.stem}{sidecar}" in names, f"{sidecar} is not an artefact"
        assert f'{{s}}{sidecar}"' in wipe, f"{sidecar} is not wiped"


def test_a_chart_adopted_as_a_verify_chart_takes_its_record_along(tmp_path):
    """`adopt_run_chart_as_verify` moves the chart into `verifications/` under
    a new stem. A record left behind at the run root would be filed against
    whatever chart lands on the profiling stem next."""
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    _chart(run, "a verification chart")
    _print_it(run)

    moved = run.adopt_run_chart_as_verify()

    assert moved is not None
    assert not print_record_path(run.chart_ti2).exists(), (
        "the record stayed at the run root while its chart moved away")
    assert (run.verifications_dir /
            f"{run.verify_stem}.print.json").is_file()
