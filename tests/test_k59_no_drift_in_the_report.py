"""K59: Knut's answers in #182 5849392788 (beta 44) on a sheet printed raw.

1. **Option C** (B8-1393). A raw sheet's cells read the words its rows hold:
   PASS or FAIL on the paper and solid rows where the set limits them (K51),
   INFO on a value shown for information, *"with a numbered reference to a
   note that explains the issue, where that is relevant"*, N-A with its note
   where the sheet cannot answer. Overall: the judged rows' word, else INFO.
   The raw print is named once, under "Judged against".
2. **"The word drift is not used at all"** (B8-1394), in the report, its
   graphs, its guide, its help, its window and its PDF, English and German;
   *"Use the word "Change" instead of "Drift""*.
3. **The openings he chose** (B8-1381 "The conditional form", B8-1383 "Ok",
   B8-1384 "Yes"), each given only where it is TRUE of exactly the rows
   judged (challenge 9 of beta 44); the mixed document's sentence without
   "drift" (B8-1380, proposed).
4. **The two FROM PROFILE GAMUT state lines** (B8-1386, "Ok"), verbatim.

The new texts (M-REPORT-RAW-*, M-REPORT-MIXED-OPENING) were APPROVED by
Knut in #182 5850164956; `tests/test_message_catalogue.py` holds that set.
K60 (his answers D1 to D3 in the same post) is pinned in
`tests/test_k60_raw_openings_and_repeatability.py`.

Every test names the mutation that turns it red; each was run red
(~/Desktop/ChromIQ-beta44-proof/k59/mutations.txt).
"""
from __future__ import annotations

import ast
import html as _html
import json
import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402

from workflow import compliance_sets as CS                     # noqa: E402
from workflow import measurement_messages as M                 # noqa: E402
from workflow import measurement_report as MR                  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
THREE = ("substrate_de00_max", "solids_de00_max", "cmy_solids_dhab_max")


def _de() -> dict:
    return json.loads((ROOT / "data/i18n/de.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _dialog(qapp):
    from tests.test_calibration_reports import _settings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    return MeasurementReportDialog(_settings())


# --------------------------------------------------------------------------
# 2. no "drift" in any text of the report, English or German
# --------------------------------------------------------------------------
def _tr_literals(path: Path, *, every_constant: bool = False) -> "list[str]":
    """The English source strings of *path*: the literal argument of every
    ``tr(...)`` call, or with *every_constant* every string constant that is
    not a docstring (compliance_sets keeps its labels and blurbs as data)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(
                    body[0].value, ast.Constant):
                docs.add(id(body[0].value))
    out = []
    for node in ast.walk(tree):
        if every_constant:
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in docs):
                out.append(node.value)
        elif (isinstance(node, ast.Call)
              and getattr(node.func, "id", None) == "tr" and node.args
              and isinstance(node.args[0], ast.Constant)
              and isinstance(node.args[0].value, str)):
            out.append(node.args[0].value)
    return out


#: Where the report and its help live. Whole files where every string is
#: about the report or about printing raw; for the two big tabs and
#: Preferences only the strings that are about the report (their other uses
#: of the word are about an instrument or a strip moving physically, which
#: is not what Knut ruled on).
_WHOLE = ("ui/dialogs/measurement_report_dialog.py",
          "ui/dialogs/welcome_dialog.py", "ui/tools_popup.py",
          "ui/file_guide.py", "ui/tabs/tab_print.py",
          "ui/measurement_target_bar.py",
          "ui/dialogs/preset_verification_dialog.py")
_ABOUT_THE_REPORT = ("ui/dialogs/settings_dialog.py", "ui/tabs/tab_measure.py")


def _report_texts() -> "list[str]":
    texts: "list[str]" = []
    for f in _WHOLE:
        texts += _tr_literals(ROOT / f)
    for f in _ABOUT_THE_REPORT:
        texts += [t for t in _tr_literals(ROOT / f)
                  if "measurement report" in t.lower()]
    texts += _tr_literals(ROOT / "workflow/compliance_sets.py",
                          every_constant=True)
    for mid, msg in M.CATALOGUE.items():
        if mid.startswith(("M-REPORT", "M-VERIFY", "M-LIMIT")):
            texts += [msg.title, msg.body] + (
                [msg.body_one] if msg.body_one else [])
    return texts


def test_no_text_of_the_report_says_drift_in_english_or_german():
    """Every string of the report window, its PDF, its graphs, its guide, its
    help and its notes, and the help texts about the report and about
    printing raw: no "drift" in English, and no "Drift" (nor "driftet",
    "abdriften") in the German each one is shown as.

    MUTATION, proven red: put ``tr("drift")`` back as the cell word of a raw
    column in `_report_results_html` (or restore any one of the old
    sentences, e.g. "Drift since the previous raw check ({prev})")."""
    de = _de()
    bad = [t for t in _report_texts() if "drift" in t.lower()]
    assert not bad, [b[:100] for b in bad]
    bad_de = [(k[:60], de[k][:100]) for k in _report_texts()
              if k in de and "drift" in de[k].lower()]
    assert not bad_de, bad_de


def test_the_guard_is_not_vacuous():
    """The scan above must reach the texts it is about.

    MUTATION, proven red: return [] from `_report_texts`."""
    texts = _report_texts()
    assert len(texts) > 1500
    for probe in (M.M_REPORT_RAW_CHANGE.body, "Judged against",
                  "Measurement report (accuracy & trends)"):
        assert probe in texts, probe


# --------------------------------------------------------------------------
# 1. option C: a raw sheet's cells, its note, its Overall, "Judged against"
# --------------------------------------------------------------------------
def _raw_sheet(k_solid: float = 5.4, paper: float = 0.4,
               profile: bool = True) -> dict:
    """A verification sheet printed raw, against the design; its paper and
    solids compared with the profile when *profile*, else not worked out."""
    rep = {"is_verification": True, "sheet_kind": "verification",
           "reference_source": "design", "printing": {"colour": "raw"},
           "de00": MR._stats([12.0 + 0.1 * i for i in range(60)])}
    if profile:
        rep["condition_reference"] = {
            "paper": {"from": MR.CONDITION_FROM_PROFILE, "de": paper},
            "solids": {"from": MR.CONDITION_FROM_PROFILE,
                       "de": {"C": 0.3, "M": 0.2, "Y": 0.1, "K": k_solid},
                       "dhab": {"C": 0.1, "M": 0.2, "Y": 0.1}}}
    return rep


def _live(dlg, monkeypatch, set_id: str):
    """The dialog judges every column against *set_id*, live."""
    from types import SimpleNamespace
    name = CS.set_label(set_id)
    got = SimpleNamespace(limits=CS.effective_limits(set_id, {}),
                          set_id=set_id, set_label=name, label_en=name,
                          edited=False)
    monkeypatch.setattr(type(dlg), "_limits_for", lambda self, r: got)


def _cells(html: str, label: str) -> str:
    """The row of the results grid that starts with *label*."""
    i = html.find(_html.escape(label) + "</td>")
    assert i >= 0, label
    return html[i:html.find("</tr>", i)]


def test_a_raw_sheets_cells_read_their_words_and_the_note(qapp, monkeypatch):
    """Under ISO 12647-7 a raw sheet judges its paper and solid rows (the
    black solid at 5.4 FAILs), and every row compared with the design reads
    INFO with the raised number of M-REPORT-RAW-PRINT-INFO, whose sentence
    is in the notes under the grid. No cell reads "drift".

    MUTATION, proven red: drop the K59 block at the end of
    `_note_the_absences` (INFO cells carry no number, the note is not
    printed)."""
    dlg = _dialog(qapp)
    try:
        _live(dlg, monkeypatch, "iso_12647_7")
        rep = _raw_sheet()
        html = dlg._report_results_html([rep])
        assert "drift" not in html.lower()
        assert ">FAIL" in _cells(html, dlg._row_name("solids_de00_max"))
        info = _cells(html, dlg._row_name("all_de00_avg"))
        assert ">INFO" in info and "<sup" in info, info
        assert _html.escape(M.M_REPORT_RAW_PRINT_INFO.body) in html
        # the Overall word follows the judged rows
        assert ">FAIL<" in _cells(html, "Overall")
    finally:
        dlg.deleteLater()


def test_the_note_is_where_it_is_relevant_and_nowhere_else(qapp,
                                                          monkeypatch):
    """The note says the value compares the print with the design colours,
    so it goes on exactly those rows: not on the paper and solid rows (the
    profile), not on the repeatability rows (readings against readings, and
    since D3, Knut #182 5850164956, JUDGED on a raw sheet), not on a sheet
    printed through its profile, and not on a Printing record, whose INFO is
    the type's doing.

    MUTATION, proven red: attach the note to every INFO row (drop the
    `ROWS_COMPARED_WITH_THE_DESIGN` test)."""
    dlg = _dialog(qapp)
    try:
        _live(dlg, monkeypatch, "chromiq_default")
        rep = _raw_sheet()
        rep["repeat_within_sheet"] = {"eligible": True, "max": 0.4,
                                      "groups": 12, "pairs": 12}
        rows, _rec = dlg._verdict_rows(rep)
        repeat = [x for x in rows if x["row_id"] == "repeat_patches_de00_max"]
        assert repeat and repeat[0]["word"] == CS.PASS, repeat
        noted = {x["row_id"] for x in rows
                 if MR.NOTE_RAW_PRINT_INFO in (x.get("notes") or ())}
        assert noted and noted <= MR.ROWS_COMPARED_WITH_THE_DESIGN, noted
        assert not noted & set(THREE)
        assert not noted & {"repeat_patches_de00_max",
                            "repeat_measurement_de00_max"}
        through = dict(rep, printing={"colour": "through-profile"})
        rows, _rec = dlg._verdict_rows(through)
        assert not any(MR.NOTE_RAW_PRINT_INFO in (x.get("notes") or ())
                       for x in rows)
    finally:
        dlg.deleteLater()


def test_judged_against_names_the_raw_print_once(qapp, monkeypatch):
    """A raw column that judged reads "<set> (printed raw)", one that judged
    nothing "not judged (printed raw)"; a column printed through the profile
    reads its set alone.

    MUTATION, proven red: give `_thresholds_cell` its "—" back for a column
    that judged nothing."""
    dlg = _dialog(qapp)
    try:
        _live(dlg, monkeypatch, "iso_12647_7")
        rep = dict(_raw_sheet(), _fresh=True)
        cell = _html.unescape(dlg._thresholds_cell(rep))
        assert "(printed raw)" in cell and "ISO 12647-7" in cell, cell
        _live(dlg, monkeypatch, "chromiq_default")
        cell = _html.unescape(dlg._thresholds_cell(rep))
        assert M.M_REPORT_RAW_NOT_JUDGED.body in cell and "—" not in cell
        through = dict(rep, printing={"colour": "through-profile"})
        assert "printed raw" not in dlg._thresholds_cell(through)
    finally:
        dlg.deleteLater()


def test_a_raw_sheet_that_judged_nothing_reads_info_with_its_own_sentence(
        qapp, monkeypatch):
    """Overall INFO, and the sentence behind it is M-REPORT-RAW-OVERALL, not
    the profiling sheet's "measured to build a profile". A report saved
    before K59 stored that sentence; it is read as the raw one (a saved
    sentence is a rendering), the word and counts as saved.

    MUTATION, proven red: drop ``else SUMMARY_REASONS["raw_print"]`` from
    `_column_summary` (the tooltip says "measured to build a profile")."""
    assert CS.SUMMARY_REASONS["raw_print"] == M.M_REPORT_RAW_OVERALL.body
    dlg = _dialog(qapp)
    try:
        _live(dlg, monkeypatch, "chromiq_default")
        rep = _raw_sheet()
        sm = dlg._column_summary(rep)
        assert sm.word == CS.INFO and sm.reason == M.M_REPORT_RAW_OVERALL.body
        saved = dict(rep, verdict={
            "rows": [], "graded": False, "overall": CS.INFO,
            "summary": {"checked": 0, "total": 3, "failed": 0, "cond": 0,
                        "not_computed": 0,
                        "reason": CS.SUMMARY_REASONS["not_graded"]}})
        sm = dlg._column_summary(saved)
        assert sm.word == CS.INFO and sm.reason == M.M_REPORT_RAW_OVERALL.body
    finally:
        dlg.deleteLater()
    rep = _raw_sheet()
    MR.stamp_verdict(rep, CS.effective_limits("chromiq_default", {}),
                     set_id="chromiq_default", set_label="d")
    assert rep["verdict"]["summary"]["reason"] == M.M_REPORT_RAW_OVERALL.body


def test_the_sentence_under_the_results_is_true_of_the_rows_judged(
        qapp, monkeypatch):
    """Knut's K51 clause, verbatim, where every raw column judged all three
    rows; "where the limit set has a limit for them and the measurement can
    answer them" where the set limits fewer (ISO 12647-8: the paper only);
    the sentence of a column that judged nothing under ChromIQ default.

    MUTATION, proven red: always print M-REPORT-RAW-RESULTS-JUDGED where a
    raw column judged (ISO 12647-8 is told its solids were judged)."""
    dlg = _dialog(qapp)
    try:
        for sid, msg in (("iso_12647_7", M.M_REPORT_RAW_RESULTS_JUDGED),
                         ("iso_12647_8", M.M_REPORT_RAW_RESULTS_SOME),
                         ("chromiq_default", M.M_REPORT_RAW_RESULTS)):
            _live(dlg, monkeypatch, sid)
            html = dlg._report_results_html([_raw_sheet()])
            said = [m for m in (M.M_REPORT_RAW_RESULTS_JUDGED,
                                M.M_REPORT_RAW_RESULTS_SOME,
                                M.M_REPORT_RAW_RESULTS)
                    if _html.escape(m.body) in html]
            assert said == [msg], (sid, [m.id for m in said])
    finally:
        dlg.deleteLater()


# --------------------------------------------------------------------------
# 3. the openings
# --------------------------------------------------------------------------
SCOPE = " The measurements it covers are listed under Report Scope."
RAW = ("This report follows the printer behind the profile built in {where}. "
       "Its sheets were printed without the profile, measured, and compared "
       "with the chart's own aim values")
ALL = RAW + "; the paper and the solid colours are judged against the profile."
WHERE = (RAW + "; the paper and the solid colours are judged against the "
         "profile where the limit set has a limit for them.")
NONE = RAW + "."
#: D1 (Knut, #182 5850164956, B8-1395): "Use the new sentence."
ANSWERABLE = (RAW + "; the paper and the solid colours are judged against "
              "the profile where the limit set has a limit for them and the "
              "measurement can answer them.")
PLURAL = ("This report follows the printers behind the profiles built in "
          "{where}. Their sheets were printed without the profiles, measured, "
          "and compared with the charts' own aim values." + SCOPE)


def _sheet(colour, run="run3", when="2026-11-16_100000", **kw):
    rep = _raw_sheet(**kw)
    rep.update(printing={"colour": colour}, chart="Demo-verify",
               ti3="Demo-verify.ti3", created="2026-11-16T10:00:00",
               _origin_dir=f"/nowhere/Demo/runs/{run}/verifications/{when}")
    return rep


def _opening(dlg, monkeypatch, set_id, runs):
    _live(dlg, monkeypatch, set_id)
    monkeypatch.setattr(type(dlg), "_report_kind",
                        lambda self, runs: "verification")
    return dlg._what_this_report_judges(runs)


@pytest.mark.parametrize("set_id,kw,want", [
    ("iso_12647_7", {}, ALL),                       # all three judged
    ("iso_12647_8", {}, WHERE),                     # the paper only limited
    ("chromiq_default", {}, WHERE),                 # none limited
    ("iso_12647_7", {"profile": False}, ANSWERABLE),  # limited, N-A (D1)
])
def test_each_raw_opening_is_given_where_it_is_true(qapp, monkeypatch,
                                                    set_id, kw, want):
    """Knut's accepted clause where every raw column judged all three rows;
    his conditional form where every limited row was judged and some are
    "–"; his D1 sentence (#182 5850164956) where a limited row read N-A. Each
    ends with the Report Scope sentence (B8-1384, "Yes").

    MUTATION, proven red: give the full clause wherever a column judged
    anything (as K56 did): ISO 12647-8 says its solids were judged."""
    dlg = _dialog(qapp)
    try:
        said = _opening(dlg, monkeypatch, set_id,
                        [_sheet("raw", **kw),
                         _sheet("raw", when="2026-11-23_100000", **kw)])
        assert said == (want + SCOPE).format(where="Demo, run 3"), said
    finally:
        dlg.deleteLater()


def test_several_runs_all_raw_and_mixed(qapp, monkeypatch):
    """Across runs, every sheet raw: Knut's plural sentence ("Ok") and the
    Report Scope sentence, with the judged clause in its plural form where a
    paper or solid row was judged (D1, K60). One run, sheets printed both
    ways: the mixed sentence without "drift" (approved). Across runs with both
    kinds: his D2 sentence (#182 5850164956, "Accepted."), B8-1397.

    MUTATION, proven red: drop the ``if _all_raw`` branch of the plural
    case (the approved "Each was verified by printing a chart through its
    profile" over sheets printed without it)."""
    dlg = _dialog(qapp)
    try:
        said = _opening(dlg, monkeypatch, "iso_12647_7",
                        [_sheet("raw", run="run1"), _sheet("raw", run="run3")])
        assert said == PLURAL.replace(
            "aim values.", "aim values; the paper and the solid colours are "
            "judged against the profiles.").format(
                where="Demo, run 1; Demo, run 3"), said
        said = _opening(dlg, monkeypatch, "iso_12647_7",
                        [_sheet("through-profile"), _sheet("raw")])
        assert said == M.M_REPORT_MIXED_OPENING.body.format(
            where="Demo, run 3"), said
        said = _opening(dlg, monkeypatch, "iso_12647_7",
                        [_sheet("through-profile", run="run1"),
                         _sheet("raw", run="run3")])
        assert said == M.M_REPORT_MIXED_OPENING_RUNS.body.format(
            where="Demo, run 1; Demo, run 3"), said
    finally:
        dlg.deleteLater()


# --------------------------------------------------------------------------
# "Change since the previous raw check" and the other chapter lines
# --------------------------------------------------------------------------
@pytest.mark.parametrize("rd,msg", [
    ({"baseline": True}, M.M_REPORT_RAW_BASELINE),
    ({"incomparable": True}, M.M_REPORT_RAW_INCOMPARABLE),
    ({"avg": 1.2, "max": 3.4, "n": 60, "prev": "2026-11-16T10:00:00"},
     M.M_REPORT_RAW_CHANGE),
    ({}, M.M_REPORT_RAW_SHEET),
])
def test_the_detailed_chapter_says_change(qapp, monkeypatch, rd, msg):
    """Under a raw sheet's table: the line for its comparison record, from
    §M, and never "drift". The table shows the rows' words (INFO with its
    note), not "—".

    MUTATION, proven red: restore the "Drift since the previous raw check"
    sentence in `_run_detail_html`."""
    dlg = _dialog(qapp)
    try:
        _live(dlg, monkeypatch, "chromiq_default")
        rep = _sheet("raw")
        rep["raw_drift"] = rd
        detail = _html.unescape(dlg._run_detail_html(rep))
        want = msg.render(prev="2026-11-16 10:00", avg="1.20", max="3.40",
                          n=60)[1] if "{" in msg.body else msg.body
        assert want in detail, detail[-600:]
        assert "drift" not in detail.lower()
        assert ">INFO<" in detail.replace("</span>", "<")
    finally:
        dlg.deleteLater()


# --------------------------------------------------------------------------
# 4. the FROM PROFILE GAMUT state lines, and the German of every new text
# --------------------------------------------------------------------------
def test_the_gamut_state_lines_are_knuts_verbatim():
    """B8-1386, Knut: "Ok", to both.

    MUTATION, proven red: restore "so it carries no colorimetric
    reference."."""
    from types import SimpleNamespace
    from ui.dialogs.preset_verification_dialog import _gamut_state_line
    assert _gamut_state_line(SimpleNamespace(from_profile_gamut=False)) == (
        "This chart was not built with From Profile Gamut, so printed through "
        "its profile its solid patches are converted.")
    assert _gamut_state_line(SimpleNamespace(from_profile_gamut=True)) == (
        "This chart was built with From Profile Gamut, so it prints its solid "
        "patches as they are.")
    de = _de()
    for k in ("This chart was not built with From Profile Gamut, so printed "
              "through its profile its solid patches are converted.",
              "This chart was built with From Profile Gamut, so it prints its "
              "solid patches as they are."):
        assert de[k] != k and "Volltonfelder" in de[k]
        assert "farbmetrische Referenz" not in de[k]


def test_every_k59_text_is_approved_and_german_by_hand():
    """The fourteen texts were APPROVED by Knut in #182 5850164956 and left
    §M-PROPOSED; each has German written by hand (not the English), no em
    dash, and no "du" in report text.

    MUTATION, proven red: mark any of them ``approved=False``; or set a German
    value back to its English key."""
    de = _de()
    assert len(M.K59_TEXTS) == 14
    for m in M.K59_TEXTS:
        assert m.approved, m.id
        assert m.id not in M.PROPOSED
        for en in (m.title, m.body):
            t = de[en]
            if en != "{set} (printed raw)":
                assert t != en, (m.id, en[:60])
            assert "—" not in en and "—" not in t, m.id
            assert not re.search(r"\b(du|dein\w*|dich|dir)\b", t), (m.id, t)
            assert "drift" not in t.lower() and "drift" not in en.lower()
