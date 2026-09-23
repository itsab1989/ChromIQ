"""#182 K28, the report-rendering half (beta 39, B8-846).

Knut, #182 5795087247 (2026-09-23), answering 5794332548:

1. the one-page summary shows the judged (within-gamut) figures, and the
   reports say that the judged figures are the within-gamut ones;
2. one name per metric, i1Profiler's word order with the unit, in the report,
   the graphs, the Report Limits window and the help texts;
3. a limit set to "–" removes the row everywhere: Report Results, How to read,
   Detailed data, the graph AND the Overview table;
4. figures that never have a limit go under "For information (no limit
   applies)";
5. a row is left out only when its limit is "–"; the numbered notes are the
   only naming of what was left out;
6. a report of several runs or projects says so under "Run description"
   (B8-798);
7. B8-845's four text questions.

Every test names the mutation it was proved red against.
"""
from __future__ import annotations

import html as _html
import os
import re
from datetime import datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                      # noqa: E402

from core.i18n import tr                                      # noqa: E402
from workflow import measurement_report as mr                 # noqa: E402
from workflow.compliance_sets import (ROW_BY_ID, ROWS, Limit,  # noqa: E402
                                      effective_limits)
import ui.dialogs.measurement_report_dialog as mrd            # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


FIVE = {
    "all_de00_avg": "Average ΔE00, all patches",
    "best95_de00_avg": "Average ΔE00, lowest 95 %",
    "worst5_de00_avg": "Average ΔE00, highest 5 %",
    "all_de00_max": "Maximum ΔE00, all patches",
    "all_de00_p95": "Maximum ΔE00, lowest 95 % (95th percentile)",
}
OLD_SPELLINGS = ("All patches, average", "Best 95 % of patches",
                 "Worst 5 % of patches", "All patches, largest",
                 "All patches, 95th percentile", "Average ΔE,", "Maximum ΔE,",
                 "Average, all", "Maximum, all", "all judged patches",
                 "Average difference", "Largest ")


def _text(body_html: str) -> str:
    return _html.unescape(re.sub(r"<[^>]+>", " ", body_html))


def _open(tmp_path, qapp, limits):
    from tests.test_trend_graphs_for_judged_metrics import _open as o
    return o(tmp_path, qapp, limits)


def _limits_with_dash(*row_ids):
    lim = dict(effective_limits("chromiq_default", {}))
    for rid in row_ids:
        lim[rid] = Limit.none()
    return lim


# ---------------------------------------------------------------------------
# 2. one vocabulary
# ---------------------------------------------------------------------------
def test_the_five_names_are_knuts_in_i1profilers_order():
    """MUTATION, proven red: put "All patches, average" back as the label of
    `all_de00_avg` in `compliance_sets.ROWS`."""
    for rid, name in FIVE.items():
        assert ROW_BY_ID[rid].label == name, rid
    order = [r.id for r in ROWS if r.group == "all_patches"]
    assert order == list(FIVE), order


def test_every_place_names_a_metric_from_rows(tmp_path, qapp):
    """The grid, How to read, the detailed table, the Overview and the graph
    legend all print the ROWS name, and none of the old spellings survives in
    the rendered report.

    MUTATION, proven red: make `_METRIC_LABELS["avg_all"]` return
    tr("Average ΔE, all patches") again (the Overview, the detail table and
    the graph disagree with the grid)."""
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        dlg._detail_check.setChecked(True)
        runs = dlg._runs_for_report()
        assert len(runs) > 1
        body = _text(dlg._report_body_html(runs, for_pdf=True))
        for old in OLD_SPELLINGS:
            assert old not in body, old
        for name in FIVE.values():
            # grid, guide, overview, detail: four places at least
            assert body.count(name) >= 4, (name, body.count(name))
        legend = [m[0] for m in dlg._trend_configs()[0][2]]
        assert legend == list(FIVE.values()), legend
        for k in mrd._ACCURACY_ROW_KEYS:
            assert mrd._METRIC_LABELS[k]() == tr(
                ROW_BY_ID[mrd._ROW_ID_OF[k]].label)
    finally:
        dlg.deleteLater()


def test_a_legend_does_not_repeat_a_unit_its_name_carries():
    """MUTATION, proven red: drop the `if unit and unit in label` early
    return from `_with_unit`."""
    assert mrd._with_unit("Average ΔE00, all patches", "ΔE00") == \
        "Average ΔE00, all patches"
    assert mrd._with_unit("Grey balance of the grey ramp, average",
                          "ΔCh").endswith("(ΔCh)")


def test_a_note_names_its_rows_apart_when_the_names_carry_commas(tmp_path,
                                                                qapp):
    """"Average ΔE00, all patches, Maximum ΔE00, all patches" cannot be read;
    the rows a note covers are joined by "; ".

    MUTATION, proven red: join with ", " in `_numbered_notes_from`."""
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        numbering = [(1, "x\x1fthe sentence",
                      ["all_de00_avg", "all_de00_max"])]
        out = dlg._numbered_notes_from(numbering)
        assert out[0][1] == ("Average ΔE00, all patches; "
                             "Maximum ΔE00, all patches"), out
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# 3. a "–" limit removes the row everywhere
# ---------------------------------------------------------------------------
def test_a_dash_row_leaves_results_guide_and_detail(tmp_path, qapp):
    """A "–" on "Average ΔE00, highest 5 %" and on the grey average: neither
    row is in Report Results, How to read or the detailed table; the rows
    next to them are.

    MUTATION, proven red: make `_drop_dash_rows` return its rows unchanged
    (both rows come back as INFO in all three places)."""
    dlg = _open(tmp_path, qapp, _limits_with_dash(
        "worst5_de00_avg", "grey_balance_neutral_ramp_avg"))
    try:
        dlg._detail_check.setChecked(True)
        runs = dlg._runs_for_report()
        results = _text(dlg._report_results_html(runs))
        guide = _text(dlg._how_to_read_html(dlg._rows_the_results_show(runs)))
        detail = _text(dlg._detailed_section_html(runs))
        for part in (results, guide, detail):
            assert "Average ΔE00, highest 5 %" not in part
            assert tr(ROW_BY_ID["grey_balance_neutral_ramp_avg"].label) \
                not in part
            assert "Average ΔE00, lowest 95 %" in part
        for r in runs:
            rows, _rec = dlg._verdict_rows(r)
            assert all(x.get("threshold") is not None for x in rows)
    finally:
        dlg.deleteLater()


def test_a_dash_row_leaves_the_overview_and_the_graph(tmp_path, qapp):
    """MUTATION, proven red: return `set()` from `_dash_row_ids` (the
    Overview and the graph keep the row)."""
    dlg = _open(tmp_path, qapp, _limits_with_dash("worst5_de00_avg"))
    try:
        runs = dlg._runs_for_report()
        overview = _text(dlg._comparison_table_html(runs))
        assert "Average ΔE00, highest 5 %" not in overview
        assert "Average ΔE00, lowest 95 %" in overview
        legend = [m[0] for m in dlg._trend_configs()[0][2]]
        assert "Average ΔE00, highest 5 %" not in legend
        assert len(legend) == 4, legend
    finally:
        dlg.deleteLater()


def test_a_dash_average_draws_no_limit_line(tmp_path, qapp):
    """`legacy_pair` answers 2.0 for a "–" average; the graph must not draw
    "Avg 2.0" for a limit nobody set.

    MUTATION, proven red: `_accuracy_thresholds` returning
    `self._thresholds()`."""
    dlg = _open(tmp_path, qapp, _limits_with_dash("all_de00_avg"))
    try:
        avg, mx = dlg._accuracy_thresholds()
        assert avg is None and isinstance(mx, float)
        de_plan = [e for e in dlg._trend_plan() if e[0] is dlg._trend_de][0]
        assert de_plan[6] == (None, mx)
        notes = dlg._trend_extras(dlg._trend_de)["line_notes"]
        assert notes[0] == "" and notes[1]
    finally:
        dlg.deleteLater()


def test_the_overall_word_does_not_move_when_a_dash_row_leaves(tmp_path, qapp):
    """Dropping a "–" row changes what is shown, not what is counted.

    MUTATION, proven red: in `set_summary`, count every row instead of the
    limit-bearing ones (`bearing = [... for r in rows]`)."""
    from workflow.compliance_sets import set_summary
    rows_with = [(Limit.value(2.0), "PASS"), (Limit.none(), "INFO")]
    rows_without = [(Limit.value(2.0), "PASS")]
    a = set_summary(rows_with, set_is_iso=False, graded=True)
    b = set_summary(rows_without, set_is_iso=False, graded=True)
    assert (a.word, a.checked, a.total) == (b.word, b.checked, b.total)


# ---------------------------------------------------------------------------
# 4. "For information (no limit applies)"
# ---------------------------------------------------------------------------
def test_figures_with_no_limit_sit_under_their_heading(tmp_path, qapp):
    """In the Overview the heading comes after the last limited row and before
    Spread, paper white, black and the eight corners; in the detailed section
    it stands before Spread and above paper white and the corners.

    MUTATION, proven red: delete the "For information (no limit applies)"
    block row from `_comparison_table_html`."""
    head = tr("For information (no limit applies)")
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        runs = dlg._runs_for_report()
        ov = _text(dlg._comparison_table_html(runs))
        i = ov.index(head)
        assert ov.rindex(FIVE["all_de00_p95"]) < i
        for fig in (tr("Spread (std. dev.)"), tr("Paper white L*"),
                    tr("Black L*")):
            assert ov.index(fig) > i, fig
        detail = _text(dlg._run_detail_html(runs[0]))
        j = detail.index(head)
        assert detail.index(tr("Spread (std. dev.)")) > j
        assert detail.count(head) == 2
        assert detail.index(tr("Paper white & darkest black")) > \
            detail.rindex(head)
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# 1. the judged figures, and the sentence that says which they are
# ---------------------------------------------------------------------------
def _split_dialog(tmp_path, qapp, monkeypatch):
    from tests.test_gamut_split_report import _measured
    s, run, ti3 = _measured(tmp_path, monkeypatch,
                            lambda labs, *a, **kw:
                            [i % 2 == 0 for i in range(len(labs))])
    rep = mr.build_report(ti3, argyll_bin="/x/bin")
    assert rep.get("gamut_split")
    dlg = mrd.MeasurementReportDialog(s, None, initial_ti3=ti3)
    return dlg, run, rep


def test_the_one_page_summary_gives_the_judged_figures(tmp_path, qapp,
                                                       monkeypatch):
    """MUTATION, proven red: read `de = r.get("de00") or {}` in
    `_one_page_html` again (the page counts every patch of the sheet beside
    the judged word)."""
    from workflow.run_compliance import set_run_report_type
    dlg, run, rep = _split_dialog(tmp_path, qapp, monkeypatch)
    try:
        set_run_report_type(run, mr.REPORT_TYPE_SUMMARY)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        text = _text(dlg._report_body_html([rep], for_pdf=True))
        judged, src = mr.graded_de00(rep)
        assert src == mr.VERDICT_SOURCE_IN_GAMUT
        assert f"Average ΔE00, all patches: {judged['avg_all']:.2f}" in text
        # the fixture measures exactly what it asked for, so the two averages
        # agree; the COUNT tells the populations apart
        assert judged["n"] < rep["de00"]["n"]
        assert tr("The judged figures are those of the patches within the "
                  "profile's gamut.") in text
        n, tot = judged["n"], rep["gamut_split"]["n_in"] + \
            rep["gamut_split"]["n_out"]
        assert f"{n} of {tot} patches" in text
        assert tr("Cube corners, for information (no limit applies)") in text
    finally:
        dlg.deleteLater()


def test_the_within_gamut_sentence_only_where_a_shown_row_uses_it(
        tmp_path, qapp, monkeypatch):
    """The Grey and tone check shows no row a split feeds, and the Printing
    record judges nothing; neither says its words judge within-gamut figures.
    The full report does.

    MUTATION, proven red: drop `and set(present or ()) & WITHIN_GAMUT_ROWS`
    from the intro condition in `_report_results_html`."""
    from workflow.run_compliance import set_run_report_type
    dlg, run, rep = _split_dialog(tmp_path, qapp, monkeypatch)
    say = "the words judge the within-gamut figures"
    try:
        for tid, expect in ((mr.REPORT_TYPE_FULL, True),
                            (mr.REPORT_TYPE_GREY, False)):
            set_run_report_type(run, tid)
            dlg._forget_limits()
            dlg._sync_limit_controls()
            present = dlg._rows_the_results_show([rep])
            text = _text(dlg._report_results_html([rep], present))
            assert (say in text) is expect, tid
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# 6. several runs or projects: the Run description (B8-798)
# ---------------------------------------------------------------------------
def _two_run_project(root, name):
    from core.file_manager import Project
    proj = Project.create(root / name, name)
    r1 = proj.current_run()
    r1.ensure_dir()
    r2 = proj.new_run()
    r2.ensure_dir()
    for r, text in ((r1, f"{name} run one"), (r2, f"{name} run two")):
        meta = r.load_meta()
        meta.description = text
        r.save_meta(meta)
    return r1, r2


def test_the_run_description_belongs_to_the_documents_own_run(tmp_path, qapp):
    """One run: THAT run's description, whichever run the window is on. Several
    runs of one project: none, and the notice. Several projects: the project
    notice.

    MUTATION, proven red: have `_scope_html` call `self._run_description()`
    without the document's runs (the window's run is printed for all)."""
    a1, a2 = _two_run_project(tmp_path, "A")
    b1, _b2 = _two_run_project(tmp_path, "B")
    dlg = _open(tmp_path / "w", qapp, effective_limits("chromiq_default", {}))
    try:
        one = [{"_origin_dir": str(a2.dir), "ti3": "x.ti3"}]
        assert dlg._run_description(one) == "A run two"
        assert dlg._several_places_notice(one) == ""
        two = one + [{"_origin_dir": str(a1.dir), "ti3": "x.ti3"}]
        assert dlg._run_description(two) == ""
        assert "several runs" in dlg._several_places_notice(two)
        across = one + [{"_origin_dir": str(b1.dir), "ti3": "x.ti3"}]
        assert "several projects" in dlg._several_places_notice(across)
        # and it is on the page, under the heading, in place of the WINDOW's
        # own run's description, which is what B8-798 printed
        own = dlg._window_limits() and dlg._run_ctx.run
        meta = own.load_meta()
        meta.description = "the window's own run"
        own.save_meta(meta)
        runs = dlg._runs_for_report()
        for r in runs:
            r["_origin_dir"] = str(a1.dir if runs.index(r) % 2 else a2.dir)
        page = _text(dlg._scope_html(runs))
        assert tr("Run description") in page
        assert "several runs" in page
        assert "A run one" not in page and "A run two" not in page
        assert "the window's own run" not in page
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# 7. B8-845's text questions
# ---------------------------------------------------------------------------
def test_the_first_measurement_note_explains_no_chromiq(tmp_path, qapp):
    """MUTATION, proven red: put "; the row is judged from the second
    measurement onward" back on `no_earlier_measurement`."""
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        s = dlg._reason_sentence("no_earlier_measurement", {})
        assert "measured chart" in s and "second" not in s and "judged" \
            not in s, s
        e = dlg._reason_sentence("evenness_empty_area",
                                 {"evenness": {"population": "all"}})
        assert "no measured patch with an aim value" in e, e
        g = dlg._reason_sentence("evenness_empty_area",
                                 {"evenness": {"population": "in_gamut"}})
        assert "within the profile's gamut" in g, g
        d = dlg._reason_sentence("no_device_values", {})
        assert "measured chart" in d and "device values" in d, d
    finally:
        dlg.deleteLater()


def test_a_measurement_without_device_values_says_so(tmp_path):
    """A fresh report of a file with no device columns gives its grey, ramp
    and gamut rows the reason `no_device_values`, never `not_computed` ("this
    value is not in this saved report", false of a report built a second ago)
    or `no_ramp` ("no tone ramp", false of a chart that may have one).

    MUTATION, proven red: delete the `else:` branch after
    `if rgb100 is not None:` in `build_report`."""
    from tests.test_report_judging import _colours, _ramp, _write_ti3
    p = tmp_path / "nodev.ti3"
    _write_ti3(p, _ramp(16) + _colours(), verification=False)
    text = p.read_text(encoding="utf-8")
    # drop the RGB columns: keep SAMPLE_ID and the colorimetric ones
    lines = text.splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith("BEGIN_DATA_FORMAT"))
    fields = lines[i + 1].split()
    keep = [j for j, f in enumerate(fields) if not f.startswith("RGB_")]
    out, in_data = [], False
    for k, ln in enumerate(lines):
        if k == i + 1:
            out.append(" ".join(fields[j] for j in keep))
            continue
        if ln.startswith("NUMBER_OF_FIELDS"):
            out.append(f"NUMBER_OF_FIELDS {len(keep)}")
            continue
        if ln.startswith("BEGIN_DATA") and not ln.startswith("BEGIN_DATA_FORMAT"):
            in_data = True
            out.append(ln)
            continue
        if ln.startswith("END_DATA") and not ln.startswith("END_DATA_FORMAT"):
            in_data = False
        if in_data and ln.strip():
            parts = ln.split()
            out.append(" ".join(parts[j] for j in keep))
            continue
        out.append(ln)
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    rep = mr.build_report(p)
    vals = mr.row_values(rep)
    for rid in ("grey_balance_neutral_ramp_avg", "ramps_30_70_dl_max",
                "surface_gamut_de00_avg", "outer_gamut_226_de00_avg"):
        assert vals[rid]["value"] is None
        assert vals[rid]["reason"] == mr.REASON_NO_DEVICE_VALUES, (
            rid, vals[rid]["reason"])


def test_the_guide_says_what_info_and_na_are_in_this_document(tmp_path, qapp):
    """The INFO bullet no longer lists "no limit on the row" (no such row is
    shown) and on a report that judges nothing it says so instead of
    promising a note that the record does not give; the N-A bullet points at
    the raised number.

    MUTATION, proven red: drop the `if _grades_nothing` alternative of the
    INFO bullet in `_how_to_read_html` (the record promises a note)."""
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        full = _text(dlg._how_to_read_html([]))
        assert "puts no limit on the row" not in full
        assert "raised number" in full
        dlg._ungraded_by_type = lambda: True
        rec = _text(dlg._how_to_read_html([]))
        i = rec.index("INFO:")
        info = rec[i:rec.index("N-A (not applicable)")]
        assert "judges nothing" in info and "names the rows" not in info, info
    finally:
        dlg.deleteLater()


def test_the_one_page_summary_has_no_list_of_unchecked_rows():
    """Option 1 (K28 items 5 and 7): the dead list code is gone.

    MUTATION, proven red: restore `_unchecked_rows_for`."""
    assert not hasattr(mrd.MeasurementReportDialog, "_unchecked_rows_for")
    assert not hasattr(mrd.MeasurementReportDialog, "_ONE_PAGE_UNCHECKED_MAX")
