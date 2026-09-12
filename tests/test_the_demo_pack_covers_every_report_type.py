"""The limit demo package must cover every report ChromIQ can produce, and it
must stop claiming it covers none.

Knut, 2026-09-11, issue #182: *"The ChromIQ-Report-Limit-Demos demo project
must be updated with found errors, as well as expanded so that all 6 report
types can be tested for thresholds and report content."*

Four of the six can be. Validation print check (ISO 12647-8) and Contract proof
check (ISO 12647-7) cannot: the figures they judge against are published in
standards ChromIQ has no permission to include, so the app declares them,
greys them and refuses them, and no demo project can make it write one. What
the package demonstrates about those two is that they are offered, refused, and
say why, and the tests below hold that line from the other side: nothing in the
generator may name one, because a plan that did would need a tolerance value
out of a standard that may not ship.

The stale claim this file exists to have stopped is a whole README section,
"REPORT TYPES ARE NOT IN HERE, AND THAT IS NOT AN OVERSIGHT ... nothing in this
ChromIQ can select one". That was true when it was written and became false in
v4.3.0-beta.4, which shipped the pulldown. It is the same fault the lock lines
kept having in the sibling file `test_the_demo_data_describes_its_own_lock_
correctly.py`: prose about the data, written by hand, outliving the code it
described. Every answer this file checks is generated.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "make_report_limit_demos.py"


@pytest.fixture(scope="module")
def gen():
    """The generator, imported as a module. It shells out to Argyll only from
    main(), so importing it costs nothing and needs no binaries."""
    spec = importlib.util.spec_from_file_location("_demo_gen_types", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_demo_gen_types"] = mod
    spec.loader.exec_module(mod)
    try:
        yield mod
    finally:
        sys.modules.pop("_demo_gen_types", None)


def _plans(gen):
    for name, plans in gen.PROJECTS:
        for i, plan in enumerate(plans, start=1):
            yield f"{name}/run{i}", plan


def _literals(func) -> "list[str]":
    """Every string literal the function passes to its line appender. The
    docstring and the comments are prose about the rule, not text a reader
    ever sees."""
    src = inspect.getsource(func)
    return re.findall(r'a\(\s*(?:f?)"((?:[^"\\]|\\.)*)"', src)


# ---------------------------------------------------------------------------
# What the package covers
# ---------------------------------------------------------------------------
def test_every_report_type_chromiq_can_produce_has_a_run(gen):
    """A type with no run behind it is a type nobody can try.

    MUTATION: delete the Grey and tone plans from PROJECTS and this goes red.
    """
    from workflow.measurement_report import REPORT_TYPE_MENU

    chosen = {plan.report_type for _rid, plan in _plans(gen)}
    missing = [name for tid, name, _b, built in REPORT_TYPE_MENU
               if built and tid not in chosen]
    assert not missing, (
        "no run in the package produces: " + ", ".join(missing)
        + ". Add a RunPlan with report_type= set to it.")


def test_no_plan_names_a_report_type_chromiq_cannot_produce(gen):
    """And the two ISO documents may not be smuggled in.

    This is the licensing line as well as a correctness one: a plan that named
    one would have to be given numbers to judge against, and those numbers are
    in standards ChromIQ may not ship. The app refuses the write one level
    down, in `set_run_report_type`; this refuses it one level up, where the
    data is designed.

    MUTATION: set any plan's report_type to REPORT_TYPE_ISO_8 and this goes
    red (and the generator would raise before writing anything).
    """
    from workflow.measurement_report import (REPORT_TYPES,
                                             report_type_is_built)

    for rid, plan in _plans(gen):
        assert plan.report_type in REPORT_TYPES, (
            f"{rid} names an unknown report type {plan.report_type!r}")
        assert report_type_is_built(plan.report_type), (
            f"{rid} asks for {plan.report_type!r}, which ChromIQ cannot "
            f"produce. A demo cannot exercise a document the app cannot "
            f"write, and building one would need a tolerance value out of a "
            f"standard that may not ship.")
        for extra in plan.also_generate:
            assert report_type_is_built(extra), (
                f"{rid} would also save a {extra!r} report, which ChromIQ "
                f"cannot produce")


def test_every_limit_set_the_window_offers_is_some_run_s_set(gen):
    """A set no run uses is a column nobody in the package is judged by.

    MUTATION: change every `chromiq_quick` plan to `chromiq_default` and this
    goes red naming Quick check.
    """
    from workflow.compliance_sets import SET_BY_ID, selectable_set_ids

    used = {plan.set_id for _rid, plan in _plans(gen)}
    missing = [SET_BY_ID[sid].label for sid in selectable_set_ids({})
               if sid not in used]
    assert not missing, (
        "no run is judged against: " + ", ".join(missing))


def test_a_run_holds_reports_of_several_types(gen):
    """Knut, 2026-09-11: *"the user may have several uses for different
    reports"*, and the window counts the types a run has produced off the
    disk. Nothing in the package exercised that line until a plan asked for
    it.

    MUTATION: empty every `also_generate` and this goes red.
    """
    several = [rid for rid, plan in _plans(gen) if plan.also_generate]
    assert several, (
        "no run saves reports of more than one type, so the window's "
        "'Already generated for this run' line has nothing to count")
    for rid in several:
        plan = dict(_plans(gen))[rid]
        kinds = {plan.report_type} | set(plan.also_generate)
        assert len(kinds) > 1, f"{rid} generates one type under two names"


# ---------------------------------------------------------------------------
# The README's own claims
# ---------------------------------------------------------------------------
def _fake_readme(gen, results=None, cov=None) -> str:
    """`readme()` with no built package behind it. Every section that reads
    the disk takes `dest=None` or an empty coverage dict and simply says less;
    the sections this file is about are written from the app's own tables."""
    return gen.readme(results or [], [], cov or {"with_value": [], "judged": [],
                                                 "shipped_judged": [],
                                                 "crossed": [], "uncrossed": []},
                      dest=None)


def test_the_readme_no_longer_says_report_types_cannot_be_selected(gen):
    """The whole stale section, in one assertion.

    It is allowed to QUOTE what it used to say, and it does, because anybody
    holding an older copy is being told something false by it. What it may not
    do is make the claim in its own voice, so the quotation has to sit in a
    sentence that marks it as past.

    MUTATION: reword the "USED TO SAY" paragraph, leaving the quotation
    standing on its own, and this goes red.

    ON THE WHOLE TEXT WITH ITS LINE BREAKS TAKEN OUT, and the first version of
    this test was not. The README is hard-wrapped at about 70 columns, so the
    quoted sentence is split across two lines and a plain `in` found nothing:
    the test was an `if` around an assertion that never ran, and it passed
    happily against every mutation. Flattened, and the presence of the quote
    is now asserted rather than assumed.
    """
    flat = " ".join(_fake_readme(gen).split())
    stale = "nothing in this ChromIQ can select one"
    assert stale in flat, (
        "the README no longer quotes the claim it used to make, so anybody "
        "holding an older copy has nothing telling them it is false")
    before = flat[:flat.index(stale)][-400:]
    assert "USED TO SAY" in before.upper(), (
        "the README repeats the claim that no report type can be chosen "
        "without marking it as something it used to say")


def test_the_readme_lists_the_built_and_unbuilt_types_from_the_app(gen):
    """Both halves of the pulldown, and neither typed.

    MUTATION: flip `built` to False on "Grey and tone check" in
    REPORT_TYPE_MENU and this goes red, because the name moves from the list
    of documents that have a run to the list of documents that cannot exist.
    """
    from workflow.measurement_report import REPORT_TYPE_MENU

    text = _fake_readme(gen)
    head = text.index("THE REPORT TYPES, AND WHY ONLY FOUR")
    section = text[head:head + 4000]
    built_at = section.index("FOUR CAN BE PRODUCED")
    unbuilt_at = section.index("TWO CANNOT")
    assert built_at < unbuilt_at

    for _tid, name, blurb, built in REPORT_TYPE_MENU:
        assert name in section, f"{name} is missing from the README"
        assert blurb in section, f"the line under {name} is missing"
        where = section.index(name)
        if built:
            assert built_at < where < unbuilt_at, (
                f"{name} can be produced but is listed under TWO CANNOT")
        else:
            assert where > unbuilt_at, (
                f"{name} cannot be produced but is listed as one that can")


def test_the_readme_quotes_the_window_s_own_refusal_sentence(gen):
    """The reason a greyed type gives, taken from the window rather than typed
    beside it.

    MUTATION: replace `not_built_line()` in readme() with the sentence spelled
    out and this goes red, because no literal in readme() may hold it.
    """
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import (REPORT_TYPE_ISO_7,
                                             REPORT_TYPE_ISO_8)

    said = gen.not_built_line()
    assert said == MeasurementReportDialog._not_built_line(REPORT_TYPE_ISO_8)
    assert said == MeasurementReportDialog._not_built_line(REPORT_TYPE_ISO_7), (
        "the two unbuilt types now give different reasons; the README quotes "
        "one of them and would be quoting it for both")
    assert said in _fake_readme(gen)

    typed = [t for t in _literals(gen.readme) if "Not available yet" in t]
    assert not typed, (
        "readme() types the refusal sentence instead of asking the window "
        "for it: " + "; ".join(repr(t) for t in typed))


def test_the_readme_never_types_a_count_it_can_compute(gen):
    """Three numbers went stale in this file in one round: the number of
    projects, the number of rows a report has, and how long a build takes. All
    three were typed, and two of them are now wrong in every copy already
    downloaded.

    MUTATION: put "Three projects." or "thirty rows" back into readme() and
    this goes red.
    """
    banned = [
        (r"\bThree projects\b", "the project count"),
        (r"\ball three projects\b", "the project count"),
        (r"\bthirty rows\b", "the report's row count"),
    ]
    for text in _literals(gen.readme):
        for pattern, what in banned:
            assert not re.search(pattern, text, re.I), (
                f"readme() types {what}: {text!r}. Compute it.")


def test_the_generator_does_not_type_a_count_in_its_own_DOCSTRING_either(gen):
    """THE SAME CLAIM, ONE FUNCTION OVER, AND THIS TEST WALKED PAST IT.

    The test above scans `readme()`'s string literals and nothing else. The
    module's own docstring opened with the number of projects, of profile runs
    and of dated verifications, and an adversarial round measured all three
    against `PROJECTS` on 2026-09-12: it said three projects, eleven runs and
    thirty-one dated verifications where the file builds six, twenty-three and
    fifty-five, and its "What is built" list named three of the six. A guard on
    one door and not the identical door beside it, in the guard itself.

    MUTATION: put "Three projects, eleven profile runs, thirty-one dated
    verifications" back at the top of `make_report_limit_demos.py` and this
    goes red. Watched, 2026-09-12.
    """
    doc = gen.__doc__ or ""
    banned = [
        (r"(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+"
         r"projects\b", "a project count"),
        (r"\b(eleven|twelve|thirteen|twenty[- ]three|\d+)\s+profile runs\b",
         "a profile-run count"),
        (r"\bdated verifications::", "a heading that carried the counts"),
    ]
    for pattern, what in banned:
        assert not re.search(pattern, doc, re.I), (
            f"the module docstring types {what}. It goes stale the next time "
            f"a project is added; `PROJECTS` is the answer.")

    # …AND THE OUTLINE HAS TO NAME EVERY PROJECT, which is the half a count
    # ban cannot express: three of the six were simply missing.
    for name, _plans in gen.PROJECTS:
        assert name in doc, (
            f"{name} is built and the docstring's outline does not mention it")


def test_the_readme_prints_no_build_time(gen):
    """A measured build time is stale the moment a run is added, AND it makes
    every rebuild differ from the archive somebody is comparing against. Two
    were printed, one rounded and one to a tenth of a second, and both were
    about a package with three projects in it.

    MUTATION: put "12.8 s" or "about fifteen seconds" back and this goes red.
    """
    for text in _literals(gen.readme):
        assert not re.search(r"\d+([.,]\d+)?\s*(s|sec|seconds|minutes)\b", text), (
            f"readme() prints a build time: {text!r}")
        assert not re.search(r"about (a few|fifteen|twenty|thirty|ten) seconds",
                             text, re.I), f"readme() prints a build time: {text!r}"


# ---------------------------------------------------------------------------
# The two rules a type applies to a report, held in the generator's own copy
# ---------------------------------------------------------------------------
def _report(**over) -> dict:
    r = {
        "is_verification": True,
        "sheet_kind": "verification",
        "reference_source": "design",
        "printing": {"colour": "through-profile", "intent": "relative"},
        "de00": {"avg_all": 1.0, "avg_low95": 0.9, "avg_high5": 2.5,
                 "max_all": 4.0, "max_low95": 1.4},
        "grey_balance": {"eligible": True, "avg": 1.8, "max": 2.2},
        "ramps_30_70": {"eligible": True, "max_dl": 3.0},
    }
    r.update(over)
    return r


def _limits():
    from workflow.compliance_sets import Limit
    return {"all_de00_avg": Limit.value(2.0),
            "best95_de00_avg": Limit.value(2.0),
            "worst5_de00_avg": Limit.value(2.0),
            "all_de00_max": Limit.value(3.0),
            "all_de00_p95": Limit.value(3.0),
            "grey_balance_neutral_ramp_avg": Limit.should(1.5),
            "grey_balance_neutral_ramp_max": Limit.should(3.0),
            "ramps_30_70_dl_max": Limit.value(2.0)}


def _crossed(gen, type_id):
    from workflow.compliance_sets import row_verdict, set_summary
    from workflow.measurement_report import row_values
    return gen._crossed_rows(_report(), _limits(), row_values, row_verdict,
                             set_summary, type_id)


def test_the_full_report_sees_every_row(gen):
    from workflow.measurement_report import REPORT_TYPE_FULL
    got = _crossed(gen, REPORT_TYPE_FULL)
    assert got["overall"] == "FAIL"
    assert set(got["crossed"]) == {"all_de00_max", "worst5_de00_avg",
                                   "grey_balance_neutral_ramp_avg",
                                   "ramps_30_70_dl_max"}


def test_a_grey_and_tone_check_sees_only_its_own_three_rows(gen):
    """The colour rows are dropped, not shown as not applicable, and the
    column's word follows the filter: a Grey and tone check reading FAIL
    because of a colour row it does not print would be a verdict about
    something the document never mentions.

    MUTATION: drop the `keep` filter from `_crossed_rows` and this goes red,
    because `all_de00_max` and `worst5_de00_avg` come back.
    """
    from workflow.measurement_report import REPORT_TYPE_GREY
    got = _crossed(gen, REPORT_TYPE_GREY)
    assert set(got["crossed"]) == {"grey_balance_neutral_ramp_avg",
                                   "ramps_30_70_dl_max"}
    assert "all_de00_max" not in got["values"]
    assert got["overall"] == "FAIL"          # the tone ramp is a requirement


def test_a_printing_record_judges_nothing_and_says_why(gen):
    """Every judged row INFO, the column INFO, and the reason the sentence
    written for T4 rather than the one about a profiling sheet.

    MUTATION: pass `graded=graded_sheet` unconditionally in `_crossed_rows`
    and this goes red, because the crossings come back.
    """
    from workflow.compliance_sets import SUMMARY_REASONS
    from workflow.measurement_report import REPORT_TYPE_RECORD
    got = _crossed(gen, REPORT_TYPE_RECORD)
    assert got["crossed"] == []
    assert got["overall"] == "INFO"
    assert got["reason"] == SUMMARY_REASONS["record_type"]
    # the numbers are not touched, only the words
    assert got["values"]["all_de00_max"] == 4.0


def test_a_row_nobody_could_measure_keeps_N_A_under_a_printing_record(gen):
    """"We could not measure this" is not a judgement being withheld."""
    from workflow.compliance_sets import row_verdict, set_summary
    from workflow.measurement_report import REPORT_TYPE_RECORD, row_values
    rep = _report(grey_balance={"eligible": False, "reason": "too_few_steps"})
    got = gen._crossed_rows(rep, _limits(), row_values, row_verdict,
                            set_summary, REPORT_TYPE_RECORD)
    assert "grey_balance_neutral_ramp_avg" not in got["values"]
    assert got["overall"] == "INFO"


def test_a_grey_check_on_a_chart_with_no_grey_ramp_judges_nothing(gen):
    """The state the third Overall clause was written for on 2026-09-11, and
    the state `Report-Types/run7` exists to put in front of a reader: limits
    on the column, and not one of them checkable.

    Without that clause this column read a green PASS under "Every value this
    limit set requires was checked and is within its limit", with nothing
    checked at all.
    """
    from workflow.compliance_sets import (SUMMARY_REASONS, row_verdict,
                                          set_summary)
    from workflow.measurement_report import REPORT_TYPE_GREY, row_values
    rep = _report(grey_balance={"eligible": False, "reason": "too_few_steps"},
                  ramps_30_70={"eligible": False, "reason": "no_ramp"})
    got = gen._crossed_rows(rep, _limits(), row_values, row_verdict,
                            set_summary, REPORT_TYPE_GREY)
    assert got["crossed"] == []
    assert got["overall"] == "N-A"
    assert got["reason"] == SUMMARY_REASONS["nothing_checked"]


# ---------------------------------------------------------------------------
# A story may not name a verdict the report did not give
# ---------------------------------------------------------------------------
def test_story_verdicts_reads_whole_words_only(gen):
    """"information" is not INFO and "passes" is not PASS.

    MUTATION: drop the lookarounds from `story_verdicts` and this goes red.

    THE CASES HAVE TO BE IN THE SAME CASE AS THE WORDS, and the first set was
    not: "information" and "passes" are lower case, the search is not, so they
    could never have matched however the boundaries were written and the test
    proved nothing about them. The words as a reader might shout them are what
    a boundary rule is actually for.
    """
    assert gen.story_verdicts("shown for INFORMATION only") == set()
    assert gen.story_verdicts("every value PASSES its limit") == set()
    assert gen.story_verdicts("the N-AVERAGE of the sheet") == set()
    assert gen.story_verdicts("the column reads PASS") == {"PASS"}
    assert gen.story_verdicts("reads COND rather than FAIL") == {"COND", "FAIL"}
    assert gen.story_verdicts("the word is N-A") == {"N-A"}
    assert gen.story_verdicts("the word is N-A.") == {"N-A"}


def test_the_words_come_from_the_app_not_from_a_list_here(gen):
    """A sixth verdict word must be caught by this guard on the day it lands,
    not walked past.

    MUTATION: add a word to `compliance_sets` and this still passes only
    because the generator asks for the tuple; hard-code the five in
    `story_verdicts` and this goes red.
    """
    import ast
    import textwrap

    src = inspect.getsource(gen.story_verdicts)
    assert "from workflow.compliance_sets import" in src, (
        "story_verdicts types the verdict words instead of importing them")
    # THE CODE, NOT THE DOCSTRING, and read as code rather than as text: the
    # docstring explains the word-boundary rule by naming two of the words,
    # which is prose about the rule and not a second copy of the list.
    fn = ast.parse(textwrap.dedent(src)).body[0]
    body = fn.body[1:] if ast.get_docstring(fn) else fn.body
    typed = [n.value for stmt in body for n in ast.walk(stmt)
             if isinstance(n, ast.Constant) and isinstance(n.value, str)
             and n.value in ("PASS", "FAIL", "COND", "INFO", "N-A")]
    assert not typed, f"story_verdicts types the verdict words: {typed}"


def test_the_generator_refuses_a_story_that_claims_the_wrong_verdict(gen):
    """The guard itself, in the function that writes a run.

    MUTATION: delete the `story_verdicts` check from `build_run` and this goes
    red.
    """
    src = inspect.getsource(gen.build_run)
    assert "story_verdicts(" in src, (
        "build_run no longer checks a story's verdict claim against the "
        "report's own word")
    assert "raise SystemExit" in src


def test_no_story_in_the_package_claims_a_verdict_for_another_document(gen):
    """Every story that names a word must be able to be about its own run.

    This cannot know the measured word without Argyll, so it checks the
    weaker half that does not need it: a story on a run whose document
    withholds every verdict may not name a graded word at all.

    MUTATION: put "reads FAIL" back into the Printing record's first story and
    this goes red.
    """
    from workflow.measurement_report import REPORT_TYPE_RECORD

    bad = []
    for rid, plan in _plans(gen):
        if plan.report_type != REPORT_TYPE_RECORD:
            continue
        for date in plan.dates:
            said = gen.story_verdicts(date.story)
            if said - {"INFO"}:
                bad.append(f"{rid}/{date.vid} says {sorted(said)}")
    assert not bad, (
        "a Printing record judges nothing, so these stories claim a word "
        "their document cannot print: " + "; ".join(bad))


# ---------------------------------------------------------------------------
# The coverage table names what is missing, not only what is there
# ---------------------------------------------------------------------------
def _fake_run(root: Path, project: str, run_id: str, report_type: str = "") -> None:
    d = root / project / "runs" / run_id
    d.mkdir(parents=True, exist_ok=True)
    meta = {"schema_version": 2}
    if report_type:
        meta["report_type"] = report_type
    (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def test_the_coverage_table_names_the_types_and_sets_nothing_covers(gen,
                                                                    tmp_path):
    """A table that lists only what is present cannot be told apart from a
    table that is short. This is the half that lets a reader check the claim
    instead of trusting it.

    MUTATION: return an empty `missing` list from `type_set_coverage` and this
    goes red.
    """
    dest = tmp_path / "D"
    _fake_run(dest, "Report-Limits-Only", "run1")     # the default type, T2
    cov = gen.type_set_coverage(dest)

    assert [r["run"] for r in cov["type_set_rows"]] == ["Only/run1"]
    assert cov["type_set_rows"][0]["type"] == "Full colour check"
    joined = " | ".join(cov["type_set_missing"])
    assert "Colour summary (one page)" in joined
    assert "Grey and tone check" in joined
    assert "Printing record (not graded)" in joined
    assert "ChromIQ tight" in joined and "Quick check" in joined
    # and never the two DOCUMENTS it cannot produce: a document ChromIQ may not
    # write is not a gap in the demo data.
    #
    # BY THE TYPE'S OWN NAME, AND THE FIRST VERSION MATCHED A SUBSTRING. It
    # looked for "ISO 12647-7" and "ISO 12647-8", which are also inside
    # "Custom ISO 12647-7" and "Custom ISO 12647-8" — two LIMIT SETS that held
    # no numbers when this was written and could not be a run's set. The moment
    # they could, a fixture with one run correctly reported both as sets
    # nothing covers, and this assertion read that as the two unbuildable
    # documents having leaked in. The set names are a true answer here and the
    # type names are the false one, so it asks for the type names.
    from workflow.measurement_report import REPORT_TYPE_MENU
    for _tid, name, _blurb, built in REPORT_TYPE_MENU:
        if not built:
            assert name not in joined, (
                f"{name} is a document ChromIQ cannot write, so its absence "
                f"from the package is not a gap and must not be listed as one")
    # the Custom SETS, by contrast, are a real gap in a fixture that uses
    # neither of them, and saying so is the table doing its job
    assert "Custom ISO 12647-7" in joined and "Custom ISO 12647-8" in joined


def test_the_coverage_table_reads_the_type_off_the_run(gen, tmp_path):
    """Off `meta.json`, not off the plan that asked for it: a run that never
    chose stores nothing, and only what is on disk is what a reader opens.

    MUTATION: read `plan.report_type` instead and this goes red, because there
    is no plan here at all.
    """
    dest = tmp_path / "D"
    _fake_run(dest, "Report-Limits-Only", "run1", "t3_grey_and_tone")
    _fake_run(dest, "Report-Limits-Only", "run2")
    cov = gen.type_set_coverage(dest)
    got = {r["run"]: r["type"] for r in cov["type_set_rows"]}
    assert got == {"Only/run1": "Grey and tone check",
                   "Only/run2": "Full colour check"}


def test_the_coverage_table_sorts_runs_by_number_not_by_name(gen, tmp_path):
    """run10 comes after run9. Sorted as text it comes after run1, which puts
    the table in an order no reader expects."""
    dest = tmp_path / "D"
    for n in (1, 2, 10):
        _fake_run(dest, "Report-Limits-Only", f"run{n}")
    cov = gen.type_set_coverage(dest)
    assert [r["run"] for r in cov["type_set_rows"]] == \
        ["Only/run1", "Only/run2", "Only/run10"]


# ---------------------------------------------------------------------------
# Every metric limit, and the rows that must NOT be faked
# ---------------------------------------------------------------------------
def test_every_row_chromiq_can_compute_is_given_a_limit_by_some_run(gen):
    """Knut, 2026-09-11: *"make sure the metrics have a value that can be
    tested against, and that all metrics limits are verified with the
    ChromIQ-Report-Limit-Demos package."*

    A row ChromIQ can compute and that nothing in the package puts a limit on
    is a row whose verdict this data can never exercise. There are eight, and
    one of them, the tone ramp, is judged by no shipped set at all, so a run
    has to type a limit into it.

    MUTATION: drop `ramps_30_70_dl_max` from every plan's edited_limits and
    this goes red.
    """
    from workflow.compliance_sets import ROWS, effective_limits

    computable = {r.id for r in ROWS if r.status in ("now", "build")}
    limited = set()
    for _rid, plan in _plans(gen):
        limited |= {k for k, v in (plan.edited_limits or {}).items()
                    if v is not None}
        for rid, lim in effective_limits(plan.set_id, {}).items():
            if lim.number is not None:
                limited.add(rid)
    missing = sorted(computable - limited)
    assert not missing, (
        "no run in the package puts a limit on: " + ", ".join(missing)
        + ". A row nothing limits cannot be tested against anything.")


def test_nothing_invents_a_number_for_a_row_chromiq_cannot_measure(gen):
    """The rule that matters more than the coverage.

    Fourteen rows need a gloss meter, nine readings at set positions, a
    climate chamber or a xenon rig. A demo that put a limit on one, or made a
    measurement look as though it had filled one, would make the shared
    fixture lie about what ChromIQ measures, and every later round is told to
    trust this fixture.

    MUTATION: put "uniformity_sd": 2.0 into any plan's edited_limits and this
    goes red.
    """
    from workflow.compliance_sets import ROW_BY_ID

    bad = []
    for rid, plan in _plans(gen):
        for row_id in (plan.edited_limits or {}):
            row = ROW_BY_ID.get(row_id)
            if row is None:
                bad.append(f"{rid} edits an unknown row {row_id!r}")
            elif row.status in ("unmeasurable", "unknown"):
                bad.append(f"{rid} puts a limit on {row.label!r}, which "
                           f"ChromIQ cannot measure ({row.status})")
    assert not bad, "; ".join(bad)


def test_every_row_the_package_cannot_test_has_a_reason(gen):
    """A gap that is explained is worth more than one filled by invention, and
    a gap nobody has explained is worth nothing at all.

    MUTATION: delete "unmeasurable" from UNCOVERABLE_ROW_STATUS and this goes
    red.
    """
    from workflow.compliance_sets import ROWS

    statuses = {r.status for r in ROWS if r.status not in ("now", "build")}
    missing = sorted(statuses - set(gen.UNCOVERABLE_ROW_STATUS))
    assert not missing, (
        "rows with status " + ", ".join(missing) + " cannot be tested by this "
        "package and nothing says why. Add the reason to "
        "UNCOVERABLE_ROW_STATUS.")


def test_every_message_the_package_cannot_reach_has_a_reason(gen):
    """The same rule for the sentences and the row reasons.

    The README prints "NOT REACHED, AND NOBODY HAS SAID WHY" for anything in
    neither list, which is a loud failure rather than a silent gap; this makes
    it a failing test as well, because a README nobody reads is not a gate.

    MUTATION: delete "empty" from UNREACHABLE_BY_DATA and this goes red.
    """
    from workflow.compliance_sets import SUMMARY_REASONS

    assert "empty" in gen.UNREACHABLE_BY_DATA, (
        "a limit set that defines no limits is one the report window refuses "
        "to offer, so no demo data can reach that sentence and something has "
        "to say so")
    for key in gen.UNREACHABLE_BY_DATA:
        if key in SUMMARY_REASONS:
            continue
        from workflow import measurement_report as _mr
        codes = {getattr(_mr, n) for n in dir(_mr) if n.startswith("REASON_")}
        assert key in codes, (
            f"{key!r} is excused but ChromIQ neither prints it as a sentence "
            f"nor gives it as a reason; drop the entry rather than leaving an "
            f"excuse for nothing")


def test_an_excuse_is_dropped_the_moment_the_package_can_reach_the_message(gen):
    """AN EXPLAINED GAP IS WORTH MORE THAN A COMPLETE TABLE; A GAP THAT IS NO
    LONGER THERE IS WORTH LESS THAN NOTHING.

    The `iso` sentence is the one every column named after a standard prints
    when nothing is over its limits. It was genuinely unreachable while the two
    Custom columns held no numbers: neither could be offered in the report
    window, so no run could be bound to one. They now start from ChromIQ's own
    numbers, a run IS bound to each, and the sentence is reached at
    Custom-Columns/run1 and run2. An excuse left standing there would tell a
    reader the package cannot show something it shows twice.

    Asked of the plans rather than of a list, so the answer moves with the data
    instead of with somebody remembering to come back.

    MUTATION: put "iso" back into UNREACHABLE_BY_DATA and this goes red; take
    away both Custom runs and it goes red the other way.
    """
    from workflow.compliance_sets import applies_a_standard

    binds_a_standard = any(applies_a_standard(plan.set_id)
                           for _rid, plan in _plans(gen))
    excused = "iso" in gen.UNREACHABLE_BY_DATA
    assert binds_a_standard != excused, (
        "a run in the package is bound to a set that applies a standard's "
        "figures, so the sentence such a column prints IS reachable and must "
        "not carry an excuse"
        if binds_a_standard else
        "no run is bound to a set that applies a standard's figures, so that "
        "sentence cannot be reached and something has to say why")


# ---------------------------------------------------------------------------
# How the sheet was printed decides two documents and one yardstick
# ---------------------------------------------------------------------------
def test_the_three_printing_states_are_all_built(gen):
    """"through-profile", "raw" and "none" are three different reports, and
    only the first was ever generated.

    MUTATION: set every plan's print_colour back to "through-profile" and this
    goes red.
    """
    states = {plan.print_colour for _rid, plan in _plans(gen)}
    assert states == {"through-profile", "raw", "none"}, (
        f"the package builds {sorted(states)}; a sheet printed raw is read as "
        f"a drift check and a sheet with no record makes the grey rows "
        f"informational, and neither is demonstrated by the other")


def test_write_print_record_writes_nothing_when_nobody_recorded_it(gen, tmp_path):
    """The "none" state is the ABSENCE of the file, not a file saying nothing.
    A record that said "we do not know" would still be a record, and the
    report's rule reads the file's existence.
    """
    gen.write_print_record(tmp_path, "chart", "2026-01-01T10:00:00", "p.icc",
                           "none")
    assert not list(tmp_path.glob("*.print.json"))

    gen.write_print_record(tmp_path, "chart", "2026-01-01T10:00:00", "p.icc",
                           "raw")
    rec = json.loads((tmp_path / "chart.print.json").read_text(encoding="utf-8"))
    assert rec["colour"] == "raw"
    assert rec["profile"] == "" and rec["intent"] == "", (
        "a raw sheet went to the printer with no profile applied, so naming "
        "one is a false record of how it was made")


def test_the_generator_picks_the_yardstick_the_report_will_use(gen):
    """A sheet is judged media-relative ONLY when it was printed through the
    profile with a white mapping intent; a raw sheet and a sheet with no
    record are judged in absolute Lab, where the same design lands about 1.8
    times larger.

    Measured: the first build of the "nobody recorded the printing" run had
    all five colour rows crossing on a design that asked for none of them.

    MUTATION: pass `relative=True` unconditionally in build_run and this goes
    red.
    """
    src = inspect.getsource(gen.build_run)
    assert 'relative=plan.print_colour == "through-profile"' in src, (
        "build_run no longer chooses the yardstick from how the sheet was "
        "printed, so a raw or unrecorded sheet gets a design laid out in the "
        "wrong space")

    # and that really is the app's own condition
    from workflow import measurement_report as mr
    app = inspect.getsource(mr.build_report)
    assert '_col == "through-profile"' in app, (
        "the report's media-relative rule no longer keys on "
        "colour == 'through-profile'; the generator's copy of it has moved")


def test_a_row_the_window_never_draws_contributes_no_reason(gen):
    """`_crossed_rows` reports the reasons a READER can see.

    A row with a "-" limit and no value carries no word, so the window never
    draws it (CH-20) and the reason it holds reaches nobody. Counting those
    made the package's coverage table claim `needs_reference_file` was
    demonstrated, by rows that are not on the page.

    MUTATION: drop the `word is not None` guard in `_crossed_rows` and this
    goes red.
    """
    from workflow.compliance_sets import Limit, row_verdict, set_summary
    from workflow.measurement_report import REPORT_TYPE_FULL, row_values

    rep = _report()
    limits = dict(_limits())
    limits["substrate_de00_max"] = Limit.none()     # a "-" on a row with no value
    got = gen._crossed_rows(rep, limits, row_values, row_verdict, set_summary,
                            REPORT_TYPE_FULL)
    assert "substrate_de00_max" not in got["shown_reasons"], (
        "a row the window does not draw contributed its reason to the "
        "coverage table")

# ---------------------------------------------------------------------------
# A column named after a standard carries its caveat, in the README too
# ---------------------------------------------------------------------------
def test_a_column_that_applies_a_standard_is_worded_as_one(gen):
    """FOUND BUILDING THE TWO CUSTOM RUNS, in this file's own generator.

    `_crossed_rows` passed `set_is_iso=False` from the day it was written,
    which was true of every set the package used then: the two Custom columns
    held no numbers and could not be a run's set. The moment they could, the
    README printed "none over a required limit; 3 not computed" for a column
    the WINDOW words differently, because a set that applies a standard's
    figures reads COND with the sentence saying those figures are applied to
    the chart YOU printed and not to that standard's own chart.

    A README describing a column named after a standard, without that sentence,
    is the fault `applies_a_standard` exists to have stopped, arriving in the
    file that documents the package.

    MUTATION: pass `set_is_iso=False` again in `_crossed_rows` and this goes
    red.
    """
    from workflow.compliance_sets import (SUMMARY_REASONS, row_verdict,
                                          set_summary)
    from workflow.measurement_report import REPORT_TYPE_FULL, row_values

    clean = _report(de00={"avg_all": 0.5, "avg_low95": 0.4, "avg_high5": 0.9,
                          "max_all": 1.2, "max_low95": 0.8},
                    grey_balance={"eligible": True, "avg": 0.4, "max": 0.6},
                    ramps_30_70={"eligible": True, "max_dl": 0.5})
    plain = gen._crossed_rows(clean, _limits(), row_values, row_verdict,
                              set_summary, REPORT_TYPE_FULL, "chromiq_default")
    assert plain["overall"] == "PASS", plain["overall"]
    assert plain["reason"] == SUMMARY_REASONS["pass"]

    named = gen._crossed_rows(clean, _limits(), row_values, row_verdict,
                              set_summary, REPORT_TYPE_FULL,
                              "custom_iso_12647_7")
    assert named["overall"] == "COND", (
        "a column holding a standard's name read the same word as ChromIQ's "
        "own, on the same numbers")
    assert named["reason"] == SUMMARY_REASONS["iso"], named["reason"]


def test_the_generator_never_edits_the_two_custom_columns(gen):
    """Their numbers are placeholders under a permission condition, and a test
    in the app pins where each one came from. This package may BIND a run to
    one and must never move one: a demo that nudged a number toward a real
    tolerance would be doing by data what the repository refuses to do in code.

    MUTATION: give either Custom run an `edited_limits` and this goes red.
    """
    from workflow.compliance_sets import SET_BY_ID

    for rid, plan in _plans(gen):
        parent = SET_BY_ID.get(plan.set_id)
        if parent is None or parent.kind != "custom":
            continue
        assert not plan.edited_limits, (
            f"{rid} is bound to {plan.set_id!r} and edits its limits. Those "
            f"values are placeholders under a permission condition; if a row "
            f"needs a different number, report it rather than changing it "
            f"here.")


def test_both_custom_columns_are_some_run_s_set(gen):
    """Knut asked for every metric limit to be verified with this package, and
    a column no run is bound to verifies nothing.

    Kept separate from the general "every set the window offers" test because
    these two are the ones that arrived empty and became selectable later, so
    the way they go missing is by nobody noticing rather than by a plan being
    deleted.

    MUTATION: point either Custom run at `chromiq_default` and this goes red.
    """
    used = {plan.set_id for _rid, plan in _plans(gen)}
    for sid in ("custom_iso_12647_7", "custom_iso_12647_8"):
        assert sid in used, f"no run is bound to {sid!r}"


def test_the_custom_runs_cross_a_row_and_come_back(gen):
    """The same standard the rest of the package is held to: a limit proved in
    both directions, not only crossed.

    Checked on the DECLARED expectations, which the generator then proves
    against the report it actually builds, so this holds without Argyll and the
    build holds the other half.

    MUTATION: empty the first date's `expect` on either Custom run and this
    goes red.
    """
    from workflow.compliance_sets import SET_BY_ID

    for rid, plan in _plans(gen):
        s = SET_BY_ID.get(plan.set_id)
        if s is None or s.kind != "custom":
            continue
        assert len(plan.dates) >= 2, f"{rid} has no second date to recover on"
        first, last = plan.dates[0], plan.dates[-1]
        assert first.expect, (
            f"{rid}'s first date crosses nothing, so its limits are never "
            f"exercised")
        assert not last.expect, (
            f"{rid}'s last date still crosses {last.expect}, so the row is "
            f"never shown coming back inside its limit")


def test_the_build_refuses_a_set_this_chromiq_does_not_offer(gen, monkeypatch,
                                                             tmp_path, capsys):
    """A set with no limit-bearing row judges nothing, so a run bound to one is
    a column of N-A whatever its measurement says, and every expectation on it
    misses.

    That is what the two Custom columns were before the round that gave them
    numbers. Without the check, a build against the wrong ChromIQ spent its
    seventeen seconds of Argyll and then printed four mismatches, which reads
    as a design that missed rather than as a package built against an app that
    cannot carry it. It now says which sets and stops before the first chart.

    MUTATION: delete the `unusable` block from `main` and this goes red.
    """
    monkeypatch.setattr(gen, "_selectable", lambda: {"chromiq_default"})
    rc = gen.main([str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 2, "the build did not refuse"
    assert "does not offer" in out, out
    for sid in ("custom_iso_12647_7", "custom_iso_12647_8"):
        assert sid in out, f"{sid} is not named in the refusal"
    assert not list(tmp_path.glob("Report-Limits-*")), (
        "the build wrote projects before refusing")


def test_the_offered_sets_are_asked_of_the_app(gen):
    """`_selectable` must read `selectable_set_ids`, not a list here: a column
    that stops being offered has to be caught the same way one that starts
    being offered is.

    MUTATION: return a literal tuple from `_selectable` and this goes red.
    """
    src = inspect.getsource(gen._selectable)
    assert "selectable_set_ids" in src, (
        "_selectable no longer asks the app which sets the window offers")


def test_the_two_custom_columns_are_compared_on_their_NUMBERS(gen):
    """AND THE FIRST VERSION OF THIS COMPARISON GOT IT BACKWARDS.

    Compared cell for cell over all thirty rows the two columns "differ", and
    the README said so. Every one of those differences is on a row carrying NO
    number, where one column shows ? or the cross and the other shows the dash,
    because the two standards write limits over different rows. On every row
    that carries a number they are identical, and it is the numbers that decide
    a verdict, so the README was telling a reader they could read one run
    against the other and learn something about the two standards. They cannot.

    MUTATION: compare `kind` as well as the number in `custom_column_facts`
    and this goes red.
    """
    facts = gen.custom_column_facts()
    if len(facts["custom_ids"]) < 2:
        pytest.skip("this ChromIQ does not offer both Custom columns")
    assert facts["custom_same_numbers"], (
        "the two Custom columns hold different numbers; the README's second "
        "fact about them is written for the case where they do not")
    assert facts["custom_shape_differs"], (
        "the two columns no longer differ in shape either, so the paragraph "
        "naming the rows they differ on has nothing to name")
    # every row they differ on must be one that cannot carry a verdict
    from workflow.compliance_sets import ROW_BY_ID, effective_limits
    a_ = effective_limits(facts["custom_ids"][0], {})
    b_ = effective_limits(facts["custom_ids"][1], {})
    by_label = {r.label: rid for rid, r in ROW_BY_ID.items()}
    for label in facts["custom_shape_differs"]:
        rid = by_label[label]
        assert a_[rid].number is None and b_[rid].number is None, (
            f"{label} is named as a shape difference but one of the columns "
            f"puts a number on it, so it CAN change a verdict")


def test_the_unfillable_rows_are_asked_of_the_row_not_listed_here(gen):
    """The three rows a ChromIQ chart cannot fill are read from each row's own
    status, so a row that becomes computable drops out of that list on its own.

    MUTATION: hard-code the three labels in `custom_column_facts` and this goes
    red.
    """
    src = inspect.getsource(gen.custom_column_facts)
    assert "ROW_BY_ID[rid].status" in src, (
        "custom_column_facts no longer asks each row whether ChromIQ can "
        "compute it")
    for typed in ("Paper white", "Solid colours", "hue difference"):
        assert typed not in src, (
            f"custom_column_facts types {typed!r} instead of deriving it")
