"""Re-challenge R2 of beta 39: the text faults the tester photographed, fixed.

Each test names the report item it guards (R2 #n) and, where it matters, the
mutation that turns it red. Texts are guarded twice: the old phrase may not
come back, and the new wording must appear in exactly the state it is true
of.
"""
from __future__ import annotations

import inspect
import json
import os
import stat
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from workflow import measurement_messages as M  # noqa: E402

DE = json.loads((ROOT / "data" / "i18n" / "de.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------------------
# #1 the run-delete refusal about reports it cannot renumber
# ---------------------------------------------------------------------------
def _three_runs(tmp_path):
    from tests.test_challenge_c_report_files import _three_runs as make
    return make(tmp_path)


def test_r2_1_the_refusal_is_a_message_with_a_headline(tmp_path):
    """MUTATION, proven red: raise the refusal with `reason=` only (as it
    was) and `message` is None."""
    import core.run_delete as rd
    from tests.test_challenge_c_report_files import _Target
    proj = _three_runs(tmp_path)
    locked = proj.root / "reports"
    os.chmod(locked, stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.raises(rd.DeleteFailed) as err:
            rd.delete_run(proj, rd.plan_for(proj, _Target("run2")))
    finally:
        os.chmod(locked, stat.S_IRWXU)
    title, body = err.value.message
    assert title == "Profile run 2 was not deleted"
    assert str(locked) in body
    # one folder: singular
    assert "in this folder:" in body and "Make it writable" in body
    assert "tried to remove" not in body


def test_r2_1_several_folders_read_as_several():
    t, b = M.CATALOGUE["M-RUN-DELETE-REPORTS-LOCKED"].render(
        n=3, folders="/a\n/b", count=2)
    assert t == "Profile run 3 was not deleted"
    assert "in these folders:" in b and "Make them writable" in b


def test_r2_1_the_bar_shows_the_message_without_the_remove_heading():
    """The list heading "This is what ChromIQ tried to remove:" belongs to the
    Trash failures only; a refusal with a message of its own never gets it.
    MUTATION: drop the `exc.message` branch and the order check fails."""
    from ui.measurement_target_bar import MeasurementTargetBar
    src = inspect.getsource(MeasurementTargetBar._on_delete_clicked)
    i_msg = src.index('getattr(exc, "message", None)')
    i_reason = src.index('getattr(exc, "reason", "")')
    assert i_msg < i_reason
    assert "exc.message[0]" in src[i_msg:i_reason]
    assert "tried to remove" not in src[i_msg:i_reason]


def test_r2_1_the_refusal_is_in_the_german_catalogue_by_hand():
    for key in (M.M_RUN_DELETE_REPORTS_LOCKED.title,
                M.M_RUN_DELETE_REPORTS_LOCKED.body,
                M.M_RUN_DELETE_REPORTS_LOCKED.body_one):
        assert DE.get(key) and DE[key] != key, key
    assert DE["Profile run {n} was not deleted"] == \
        "Profillauf {n} wurde nicht gelöscht"


# ---------------------------------------------------------------------------
# #2 the ISO verdict note and the How-to-read paragraph
# ---------------------------------------------------------------------------
def test_r2_2_the_caveat_makes_no_conformance_claim_and_no_stale_one():
    from workflow import compliance_sets as cs
    text = cs.STANDARD_CAVEAT
    assert "would likely meet" not in text
    assert "may differ from that standard's published" not in text
    assert "not proof" in cs.STANDARD_CAVEAT_PROOF
    assert "printed test chart" in cs.STANDARD_CAVEAT_APPLIED


def test_r2_2_the_how_to_read_paragraph_only_where_a_standard_is_named(qapp):
    """MUTATION, proven red: print the paragraph whatever `standard` says."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    stub = type("S", (), {"_ungraded_by_type": lambda self: False})()
    plain = MeasurementReportDialog._how_to_read_html(stub, [])
    iso = MeasurementReportDialog._how_to_read_html(stub, [], standard=True)
    needle = "A column named after a standard is judged"
    assert needle not in plain
    assert needle in iso
    for text in (plain, iso):
        assert "would likely meet" not in text
        assert "may differ from the standard" not in text


def test_r2_2_the_guide_asks_the_same_question_as_the_note():
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    src = inspect.getsource(MeasurementReportDialog._report_body_html)
    assert "standard=any(self._names_a_standard(r)" in src


# ---------------------------------------------------------------------------
# #7, #8, #9 counts and remedies
# ---------------------------------------------------------------------------
def test_r2_7_not_writable_follows_the_number_of_folders():
    """MUTATION, proven red: drop `body_one` and one folder reads "those"."""
    msg = M.CATALOGUE["M-REPORT-NOT-WRITABLE"]
    one = msg.render(folders="/a", count=1)[1]
    two = msg.render(folders="/a\n/b", count=2)[1]
    assert "change that folder" in one and "those folders" not in one
    assert "change those folders" in two and "that folder" not in two


def test_r2_8_the_delete_remedy_names_the_project_only_inside_one(tmp_path):
    proj = tmp_path / "P"
    (proj / "runs" / "run1" / "reports").mkdir(parents=True)
    (proj / "project.json").write_text("{}", encoding="utf-8")
    inside = proj / "runs" / "run1" / "reports" / "report_x.json"
    assert "copy the project" in M.report_delete_remedy(inside)
    beside = tmp_path / "reports" / "doc_x.json"
    (tmp_path / "reports").mkdir()
    rem = M.report_delete_remedy(beside)
    assert "copy the project" not in rem
    assert str(tmp_path) in rem
    t, b = M.CATALOGUE["M-REPORT-DELETE-FAILED"].render(
        folder=str(beside.parent), remedy=rem)
    assert "{" not in b and str(tmp_path) in b


def test_r2_8_the_window_passes_the_remedy():
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    src = inspect.getsource(MeasurementReportDialog._on_delete_report)
    assert "remedy=M.report_delete_remedy(" in src


def test_r2_9_the_calibration_reason_counts_what_is_ticked():
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    src = inspect.getsource(MeasurementReportDialog)
    assert "Untick them to save a report of the calibrations" in src
    assert "if len(_not_cal) == 1 else tr(" in src
    key = ("With Run type Calibration, a report covers calibrations only, "
           "and {n} measurements of profile runs are ticked. Untick them to "
           "save a report of the calibrations. Save report as PDF… saves the "
           "report shown here.")
    assert "{n} Messungen" in DE[key]


# ---------------------------------------------------------------------------
# #10 the greyed-Generate reason is shown whole
# ---------------------------------------------------------------------------
def test_r2_10_the_reason_is_never_shortened(qapp):
    """MUTATION, proven red: put `_wrap_beside_the_pulldown` back and the long
    German reason ends in an ellipsis."""
    from PyQt6.QtWidgets import QLabel
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    label = QLabel()
    label.resize(300, 20)
    stub = type("S", (), {})()
    stub._generate_why = label
    stub.width = lambda: 800
    full = DE["No measurement is ticked in the list, so there is nothing to "
              "report on. Tick one to generate a report."] * 3
    MeasurementReportDialog._set_generate_why(stub, full)
    assert label.text() == full
    assert label.wordWrap()


def test_r2_10_the_reason_has_a_row_of_its_own():
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    src = inspect.getsource(MeasurementReportDialog)
    assert "actions_row.addWidget(self._generate_why" not in src
    assert "top_v.addWidget(self._generate_why)" in src


# ---------------------------------------------------------------------------
# #12, #13 page breaks
# ---------------------------------------------------------------------------
def _doc(html, width=600.0, body_h=400.0):
    from PyQt6.QtCore import QSizeF
    from PyQt6.QtGui import QTextDocument
    doc = QTextDocument()
    doc.setHtml(html)
    doc.setPageSize(QSizeF(width, body_h))
    return doc


def test_r2_12_a_spacer_before_a_forced_break_takes_no_sheet(qapp):
    """A block that fills page 1, its spacer spilling onto page 2, then a
    heading that breaks before itself: three pages, the second blank.
    MUTATION, proven red: make `no_blank_page_before_a_break` return 0."""
    from ui.pdf_layout import settled_layout
    body_h = 400.0
    fill = "<div style='font-size:12px'>" + "<br>".join(
        f"line {i}" for i in range(200)) + "</div>"
    probe = _doc(fill, body_h=body_h)
    settled_layout(probe)
    # trim the filler so it ends a few px above the foot of a page
    lines = 200
    while True:
        h = probe.documentLayout().documentSize().height()
        if (h % body_h) > body_h - 20 or lines < 5:
            break
        lines -= 1
        probe = _doc("<div style='font-size:12px'>" + "<br>".join(
            f"line {i}" for i in range(lines)) + "</div>", body_h=body_h)
    spacer = "<p style='font-size:30px;margin:0'>&nbsp;</p>"
    head = ("<div style='page-break-before:always;font-weight:bold'>"
            "Next section</div><div>text</div>")
    doc = _doc("<div style='font-size:12px'>" + "<br>".join(
        f"line {i}" for i in range(lines)) + "</div>" + spacer + head,
        body_h=body_h)
    _assert_one_sheet_saved(doc, body_h)


def test_r2_12_the_same_after_a_table(qapp):
    """The report's own shape: the last trend graph is a one-cell TABLE, and
    Qt leaves an empty block where its frame ends, still on the full page, in
    front of the spacer that spilled. The first cut of the rule took that
    empty block as the start of the run and moved nothing (driven on the
    German calibration report, page 7 of 8 still blank)."""
    from ui.pdf_layout import settled_layout
    body_h = 400.0
    spacer = "<p style='font-size:30px;margin:0'>&nbsp;</p>"
    head = ("<div style='page-break-before:always;font-weight:bold'>"
            "Next section</div><div>text</div>")
    for lines in range(40, 5, -1):
        cell = "<table cellspacing='0' cellpadding='0'><tr><td>" + \
            "<br>".join(f"line {i}" for i in range(lines)) + "</td></tr></table>"
        probe = _doc(cell, body_h=body_h)
        h = settled_layout(probe).documentSize().height()
        if body_h - 25 < h <= body_h - 2:
            break
    else:
        pytest.skip("no table height ended just above the page foot")
    doc = _doc(cell + spacer + head, body_h=body_h)
    _assert_one_sheet_saved(doc, body_h)


def _assert_one_sheet_saved(doc, body_h):
    from ui.pdf_layout import no_blank_page_before_a_break, settled_layout
    settled_layout(doc)
    before = doc.pageCount()
    moved = no_blank_page_before_a_break(doc, body_h)
    settled_layout(doc)
    assert moved == 1
    assert doc.pageCount() == before - 1


def test_r2_12_and_13_the_report_pdf_applies_both_rules():
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    src = inspect.getsource(MeasurementReportDialog._export_pdf)
    assert "avoid_orphan_headings(doc, body_h)" in src
    assert "no_blank_page_before_a_break(doc, body_h)" in src
    assert src.index("_paginate_tables(doc, body_h)") < \
        src.index("no_blank_page_before_a_break(doc, body_h)")


def test_r2_13_a_heading_over_lines_follows_them_overleaf(qapp):
    """The shape of the ISO 12647-8 page 9: two bold headings at the foot of
    a page, the lines they head overleaf. After the rule both are on the
    page of their lines."""
    from ui.pdf_layout import (_line_page, avoid_orphan_headings,
                               settled_layout)
    body_h = 300.0
    for n in range(10, 40):
        html = ("<div>" + "<br>".join(f"filler {i}" for i in range(n))
                + "</div>"
                "<div style='font-weight:bold'>For information</div>"
                "<div style='font-weight:bold'>Paper white</div>"
                "<div>White L* 95</div><div>Black L* 1</div>")
        doc = _doc(html, body_h=body_h)
        lay = settled_layout(doc)
        blocks = []
        b = doc.begin()
        while b.isValid():
            blocks.append(b)
            b = b.next()
        by = {bl.text(): bl for bl in blocks}
        if (_line_page(lay, by["Paper white"], body_h)
                < _line_page(lay, by["White L* 95"], body_h)):
            break
    else:
        pytest.skip("no filler length put the headings at a page foot")
    avoid_orphan_headings(doc, body_h)
    lay = settled_layout(doc)
    b = doc.begin()
    pages = {}
    while b.isValid():
        pages[b.text()] = _line_page(lay, b, body_h)
        b = b.next()
    assert pages["For information"] == pages["Paper white"] == \
        pages["White L* 95"]


# ---------------------------------------------------------------------------
# #14, #15 measurements, not runs
# ---------------------------------------------------------------------------
def test_r2_14_a_calibration_header_counts_measurements(tmp_path):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    cal = tmp_path / "P" / "cal"
    cal.mkdir(parents=True)
    (cal.parent / "project.json").write_text("{}", encoding="utf-8")
    runs = [{"chart": "P-cal", "_origin_dir": str(cal),
             "created": f"2027-01-2{i}T10:00:00"} for i in (0, 1)]
    units = MeasurementReportDialog._scope_header_units(None, runs)
    assert any("2 measurements" in u for u in units), units
    assert not any("measurement runs" in u for u in units), units


def test_r2_15_the_list_header_counts_measurements():
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    src = inspect.getsource(MeasurementReportDialog._rebuild_from_sources)
    assert 'tr("runs")' not in src and 'tr("run")' not in src


# ---------------------------------------------------------------------------
# #16 to #19 German, and the English that read badly
# ---------------------------------------------------------------------------
def _run_delete_keys() -> "list[str]":
    import ast
    tree = ast.parse((ROOT / "core" / "run_delete.py").read_text(
        encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "tr"
                and node.args and isinstance(node.args[0], ast.Constant)):
            out.append(node.args[0].value)
    return out


@pytest.mark.parametrize("word", ["Durchgang", "Durchgäng", "Durchlauf",
                                  "Durchläuf", "Prüf-Termin", "numeriert",
                                  "Numerierung"])
def test_r2_16_the_run_delete_windows_say_lauf(word):
    """The controls say "Lauf"; the windows about deleting one say it too."""
    bad = [k for k in _run_delete_keys() if word in DE.get(k, "")]
    assert not bad, bad


@pytest.mark.parametrize("key,word", [
    ("{project}, run {run}, {when}: {why}", "Durchgang"),
    ("Already generated for this run: {names}", "Durchlauf"),
    # K31 (B8-893): "Default for new runs" became "Default for new
    # reports" and "Default for this run"; the run's own row says Lauf.
    ("Default for this run", "Durchlauf"),
    ("Delete run {n}", "Durchgang"),
])
def test_r2_16_the_photographed_lines_say_lauf(key, word):
    assert word not in DE[key]
    assert "Lauf" in DE[key] or "Läufe" in DE[key]


def test_r2_16_no_english_run_in_german_text_changed_since_ae4d79e6():
    import re
    for key in ("ChromIQ can judge this row on any VERIFICATION sheet it "
                "built, because every patch carries the colour it was asked "
                "for. A run's own profiling chart is printed raw before a "
                "profile exists, so its numbers are shown for information "
                "only and no row on it is judged. A measurement with no "
                "reference values at all is not judged either, and the "
                "report says so.",
                "Nothing needs changing on the chart: any verification sheet "
                "ChromIQ builds can be judged on this row. If it is blank, "
                "the measurement is either the run's own profiling sheet, "
                "which is not graded, or a file with no reference values, "
                "and the report says which."):
        # K31-B (B8-903) grew the first of these by a "within gamut"
        # paragraph, so the key is the sentence the R2 fix changed and
        # whatever follows it.
        keys = [k for k in DE if k.startswith(key)]
        assert keys, key[:60]
        for k in keys:
            assert not re.search(r"\bRuns?\b", DE[k]), DE[k]


def test_r2_16_the_renumbering_sentence_has_german_word_order():
    v = DE["Your other runs are renumbered, so after this deletion {move}."]
    assert v.endswith("Nach dieser Löschung gilt: {move}.")
    assert DE["run {old} becomes run {new}"] == "Lauf {old} wird zu Lauf {new}"


def test_r2_17_report_text_uses_one_word_each():
    assert "Vorgabe" not in DE[
        "How far the bare paper of the printed test chart sits from the "
        "paper the reference describes. A paper that is bluer, warmer or "
        "darker than the aim moves every colour printed on it."]
    for key in ("Where a sheet is split this way, the verdict words of the "
                "colour-accuracy and evenness rows judge the within-gamut "
                "figures.",):
        assert "Blatt" not in DE[key] and "Bogen" in DE[key]
    assert DE["{total} patches were measured and {n} of them fall inside the "
              "profile's gamut; at least 20 inside it are needed to split off "
              "the highest 5 %"].startswith("{total} Messfelder")


def test_r2_19_the_english_reads_as_english():
    from workflow import compliance_sets as cs
    blurbs = " ".join(r.blurb for r in cs.ROWS)
    assert "where the test chart used asked for it" not in blurbs
    assert "the test chart used declares" not in blurbs
    assert "geänderte Tabelle" in DE[
        "ChromIQ is back to what it ships. Close and reopen the Report "
        "limits window to see the table change."]


# ---------------------------------------------------------------------------
# #20 the report glossary is about the report, and true of a calibration
# ---------------------------------------------------------------------------
def test_r2_20_the_glossary_speaks_about_the_report(qapp):
    """MUTATION, proven red: print the gamut paragraph whatever `split`
    says, or the profile's chain in a calibration report."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    stub = type("S", (), {"_ungraded_by_type": lambda self: False})()
    f = MeasurementReportDialog._how_to_read_html
    plain = f(stub, [])
    split = f(stub, [], split=True)
    cal = f(stub, [], calibration=True)
    for text in (plain, split, cal):
        assert "it asks the run" not in text
        assert "Judging the profile on its own" not in text
    assert "Within the profile" not in plain
    assert "Within the profile" in split
    assert "profile&#x27;s conversion" not in cal and \
        "profile's conversion" not in cal
    assert "one profile holds up over time" not in cal
    assert "one profile holds up over time" in plain


# ---------------------------------------------------------------------------
# #21 the demo README is written for its reader
# ---------------------------------------------------------------------------
def test_r2_21_the_reader_filter_takes_the_developer_references_out():
    import make_release_demo_package as P
    sample = ("report lives, each from more than one side (#182, Knut "
              "5795310999).\n"
              "* **run4** (#182 E2, beta 38), Knut's preset\n"
              "  since Knut lowered the floor to 60 % (5792912682) the page\n"
              "  (#182 K29, so each row is tripped on more than one chart);\n"
              "WHERE A REPORT LIVES (K23, Report-Limits-Report-Folders)\n")
    out = P.for_the_reader(sample)
    assert not P.developer_notes_in(out), out
    assert "(so each row is tripped on more than one chart)" in out
    assert "(Report-Limits-Report-Folders)" in out


def test_r2_21_the_package_readme_carries_no_developer_note():
    """The README as `build` writes it, from the generators' own text with no
    package behind it. MUTATION, proven red: return the text unfiltered from
    `package_readme`, or put the "Built for issue #182" paragraph back."""
    import make_release_demo_package as P
    import make_report_limit_demos as G
    limit = G.readme([], [], {"with_value": [], "judged": [],
                              "shipped_judged": [], "crossed": [],
                              "uncrossed": []}, dest=None)
    m = {"package": "ChromIQ-Demo-Projects_v0", "projects": [], "papers": [],
         "metrics": [], "spec_index": []}
    text = P.package_readme(m, limit, [], [])
    assert not P.developer_notes_in(text), P.developer_notes_in(text)[:5]
    assert "seen on screen" not in text and "each a round" not in text


def test_r2_the_not_certification_note_reads_dash_and_question_mark_as_the_legend():
    """Since §23 a shipped set shows "–" for a row the standard does not
    limit, and "?" only where it limits the row with no number supplied; the
    note said "reads ? where neither is so". MUTATION: put that clause back."""
    body = M.CATALOGUE["M-THRESHOLDS-NOT-CERTIFICATION"].body
    assert "reads ? where neither is so" not in body
    # B8-979 (Knut, #182 5815435713): "–" is said only of a row ChromIQ can
    # measure; one it cannot reads ✕ in every set.
    assert "reads “–” for a row ChromIQ can measure that the standard puts no limit on" in body
    assert "? where it limits the row but no number has been supplied" in body
    de = DE[body]
    assert "wo beides nicht zutrifft" not in de
    assert "„–“" in de and "keine Zahl bereitgestellt" in de
