"""Report text names no feature, action or button of the app (K39-1).

Knut, #182 5831246553 (2026-09-25), of M-REPORT-WORKED-OUT-EARLIER's last
sentence, "Update works the report out again.":

    *"It refers to features, actions or buttons in the app interface, which
    shall never be part of the notes or the report text. Make sure all
    reports and notes do not directly mention such things, but if helpful for
    a user or customer to understand instead mentions topics in a general
    term without referring to features, actions or buttons in the app
    interface."*

(`docs/design/measurement_report_limits.md` §19.1 and §35.) A report may be
handed to a customer who has never seen ChromIQ; a window may name its own
controls. So this file scans every place report text comes from:

1. every ``tr()`` literal inside the functions that compose the report's
   page, its PDF and its graphs (`REPORT_FUNCTIONS`, each of which must still
   exist, so the list cannot rot in silence);
2. the tables those functions print from: the metric names and blurbs, the
   standard caveat, the summary reasons, the graph descriptions and the limit
   line notes;
3. every §M message the catalogue marks as printed in a report;
4. the report body itself, composed in the window and for the PDF, on a
   graded report, a Printing record and a saved report read back.

A hit that is genuinely not a reference to the app goes into `ALLOWED` with
the reason, never into the pattern.
"""
from __future__ import annotations

import ast
import html as _html
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
DIALOG = ROOT / "ui" / "dialogs" / "measurement_report_dialog.py"
CATALOGUE_DOC = ROOT / "docs" / "design" / "unified_measurement_management.md"

#: What a sentence about the app's INTERFACE looks like: its controls by
#: name, the words for controls, and the verbs a reader operates them with.
#: "press" alone is not here: "a press or a proof" is printing vocabulary.
UI_WORDS = re.compile(
    r"\b(?:click|clicks|clicked|clicking|button|buttons|pulldown|"
    r"drop-?down|checkbox|tick box|menu|toolbar|dialog|tab|tabs|"
    r"tick|ticks|ticked|untick|unticked|choose|chose|chosen|reopen)\b"
    r"|\bpress(?:es|ed)?\s+(?:the\b|“|\")"
    r"|\b(?:Generate|Update|Create New|Cancel)\b"
    r"|\bgenerate\s+(?:the|a|this)\s+(?:report|chart|verification)"
    r"|Preferences|Edit limits|Report shown|New report…|"
    r"Add Profile's Measurements|Remove Profile's Measurements|Clear List|"
    r"Select all|Deselect all|Save report as PDF|Delete Selected Report|"
    r"Show detailed data|Create Chart|Print Chart|Measure tab|"
    r"Build ICC profile|Check & Refine|Reference values…|Restore defaults|"
    r"Unlock this run",
    re.IGNORECASE)
#: The four words that are control names only when capitalised.
_CASED = {"generate", "update", "create new", "cancel"}

#: The functions of the report window that compose report text: the page,
#: the PDF, the notes and the graphs. Window-only text (the empty page, the
#: red line, tooltips, the settings help) is composed elsewhere.
REPORT_FUNCTIONS = (
    "_scope_html", "_worked_out_earlier_html", "_scope_deleted_runs_html",
    "_scope_notes_html", "_scope_warnings_html", "_several_places_notice",
    "_how_to_read_html", "_report_results_html", "_notes_list_html",
    "_comparison_table_html", "_report_body_html", "_one_page_evenness_html",
    "_one_page_html", "_swatch_table_html", "_printing_block_html",
    "_run_detail_html", "_detailed_section_html", "_reason_sentence",
    "_note_sentence", "_note_the_absences", "_control_strip_sentence",
    "_evenness_noise_sentence", "_limit_line_note", "_trend_withheld_reason",
    "_TREND_ABOUT_DE_JUDGED", "_TREND_ABOUT_DE_WITHIN_GAMUT",
    "empty_reason", "descriptions",
)

#: Exceptions, each with its reason. Keyed by a phrase of the text.
ALLOWED: "dict[str, str]" = {
    # _TrendChart.empty_reason: shown only in the window's graph area, and
    # only when the report judges none of the graph's rows; such a graph is
    # hidden in the tab bar and never printed (`_trend_plan`, `shown`).
    "Choose a report type or a limit set that judges them":
        "window only: a graph the report judges nothing of is never printed",
    # the same, for one measurement: the PDF carries no graph at all then
    # (`_export_pdf` draws graphs only when there is a trend).
    "Add another measurement, or tick more of the measurements":
        "window only: with one measurement the PDF carries no graph",
    "“Select all” ticks every one of them":
        "window only: with one measurement the PDF carries no graph",
    # A tooltip on a saved COND cell: a `title` attribute, shown on hover in
    # the window and never printed.
    "Generate the report again to have it judged by today's rule":
        "a tooltip on the page, never printed (window text)",
}


def _allowed(text: str) -> bool:
    return any(k in text for k in ALLOWED)


def ui_hits(text: str) -> list:
    """The UI words in *text*, cased words only when capitalised mid-text."""
    out = []
    for m in UI_WORDS.finditer(text or ""):
        w = m.group(0)
        if w.lower() in _CASED and not w[0].isupper():
            continue
        out.append(w)
    return out


def _offending(texts) -> list:
    return [(t, ui_hits(t)) for t in texts
            if ui_hits(t) and not _allowed(t)]


# ---------------------------------------------------------------------------
# 1. the tr() literals of the report's own functions
# ---------------------------------------------------------------------------
def _literal(node) -> "str | None":
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = _literal(node.left), _literal(node.right)
        if a is not None and b is not None:
            return a + b
    return None


def report_function_literals() -> "dict[str, list[str]]":
    tree = ast.parse(DIALOG.read_text(encoding="utf-8"))
    found: "dict[str, list[str]]" = {}
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef) or fn.name not in \
                REPORT_FUNCTIONS:
            continue
        lits = found.setdefault(fn.name, [])
        for n in ast.walk(fn):
            if (isinstance(n, ast.Call) and getattr(n.func, "id", None) == "tr"
                    and n.args):
                s = _literal(n.args[0])
                if s:
                    lits.append(s)
    return found


def test_every_report_function_still_exists():
    """The list is the scan: a function renamed away would leave its text
    unscanned in silence."""
    missing = set(REPORT_FUNCTIONS) - set(report_function_literals())
    assert not missing, f"no longer in the dialog: {sorted(missing)}"


def test_no_report_function_names_the_app():
    """MUTATION, proved to land: put "reopen this report" back into the
    colorimetric-missing paragraph of `_run_detail_html` (red)."""
    bad = []
    for name, lits in report_function_literals().items():
        bad += [(name, t[:120], h) for t, h in _offending(lits)]
    assert not bad, "report text naming the app:\n" + "\n".join(map(str, bad))


# ---------------------------------------------------------------------------
# 2. the tables the report prints from
# ---------------------------------------------------------------------------
def _tables() -> "list[str]":
    import ui.dialogs.measurement_report_dialog as mrd
    from workflow import compliance_sets as cs
    out = []
    for r in cs.ROWS:
        out += [r.label, r.blurb or ""]
    out += [cs.STANDARD_CAVEAT, cs.STANDARD_CAVEAT_PROOF]
    out += list(cs.SUMMARY_REASONS.values())
    out += [f() for f in mrd._TREND_ABOUT.values()]
    for rid, note in mrd._LIMIT_NOTES.items():
        out.append(note("NAME"))
    return out


def test_the_tables_a_report_prints_from_name_no_part_of_the_app():
    bad = _offending(_tables())
    assert not bad, "report text naming the app:\n" + "\n".join(
        f"{t[:120]!r} {h}" for t, h in bad)


# ---------------------------------------------------------------------------
# 3. the §M messages printed in a report
# ---------------------------------------------------------------------------
def report_message_ids() -> "list[str]":
    """Every §M message whose heading says it is printed in a report:
    "(window and PDF)", "report text", or "Report Scope"."""
    ids = []
    for line in CATALOGUE_DOC.read_text(encoding="utf-8").splitlines():
        m = re.match(r"### (M-[A-Z0-9-]+) · ", line)
        if m and re.search(r"window and PDF|report text|Report Scope", line):
            ids.append(m.group(1))
    return ids


def messages_the_report_functions_print() -> "set[str]":
    """The §M ids the report's own functions render: every ``M_…`` object
    they name and every ``CATALOGUE["M-…"]`` they index, so a message printed
    in a report is scanned even when its catalogue heading does not say so
    (M-REPORT-PATCH-COUNTS-DIFFER's does not)."""
    from workflow import measurement_messages as M
    tree = ast.parse(DIALOG.read_text(encoding="utf-8"))
    ids: "set[str]" = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef) or fn.name not in \
                REPORT_FUNCTIONS:
            continue
        for n in ast.walk(fn):
            name = (n.id if isinstance(n, ast.Name)
                    else n.attr if isinstance(n, ast.Attribute) else None)
            if name and name.startswith("M_"):
                obj = getattr(M, name, None)
                if isinstance(obj, M.Message):
                    ids.add(obj.id)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) \
                    and n.value in M.CATALOGUE:
                ids.add(n.value)
    return ids


def test_the_catalogue_names_its_report_messages():
    ids = report_message_ids()
    for must in ("M-REPORT-WORKED-OUT-EARLIER", "M-REPORT-NO-PAPER-PATCH",
                 "M-REPORT-SCOPE-RUN-DELETED", "M-LIMIT-RECOMMENDED"):
        assert must in ids, (must, ids)


def test_no_message_printed_in_a_report_names_the_app():
    """MUTATION, proved to land: put "; Update works the report out again."
    back on M-REPORT-WORKED-OUT-EARLIER (red)."""
    from workflow import measurement_messages as M

    class _Any(dict):
        def __missing__(self, key):
            return "X"
    bad = []
    for mid in sorted(set(report_message_ids())
                      | messages_the_report_functions_print()):
        m = M.CATALOGUE[mid]
        bodies = [m.body] + ([m.body_one] if m.body_one else [])
        for b in bodies:
            text = b.format_map(_Any())
            if ui_hits(text) and not _allowed(text):
                bad.append((mid, ui_hits(text)))
    assert not bad, bad


# ---------------------------------------------------------------------------
# 4. the report itself
# ---------------------------------------------------------------------------
def _body_text(dlg, for_pdf: bool) -> str:
    body = dlg._report_body_html(dlg._runs_for_report(), for_pdf=for_pdf)
    return " ".join(_html.unescape(re.sub(r"<[^>]+>", " ", body)).split())


def _sentences(text: str) -> "list[str]":
    return [s for s in re.split(r"(?<=[.!?:])\s+", text) if s]


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("which", ["graded", "record", "saved-earlier"])
def test_the_report_names_no_part_of_the_app(qapp, tmp_path, which):
    """The page in the window and the PDF's body, detail on, of a graded
    report of two dates, of a Printing record, and of a saved report an
    earlier version worked out (M-REPORT-WORKED-OUT-EARLIER on it).

    MUTATION, proved to land: as the §M test's (red on "saved-earlier")."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from tests.test_beta37_round_fixes import (_settings,
                                               _stamped_profiling_run)
    from tests.helpers.report_window import choose_report_type
    from workflow import measurement_report as mr
    if which == "graded":
        from tests.test_report_window_limit_controls import _verified_run
        _proj, _run, ti3s = _verified_run(tmp_path, dates=2)
        dlg = MeasurementReportDialog(_settings(tmp_path), None,
                                      initial_ti3=ti3s[-1])
    elif which == "record":
        _run, ti3 = _stamped_profiling_run(tmp_path, "chromiq_default",
                                           "ChromIQ default (recommended)")
        dlg = MeasurementReportDialog(_settings(tmp_path), None,
                                      initial_ti3=ti3)
    else:
        import ui.dialogs.measurement_report_dialog as mrd
        from tests.test_c5_a_saved_report_is_its_own_record import _window
        dlg, _run, _vs = _window(tmp_path, qapp)
        for r in dlg._runs_for_report():
            r[mrd.WORKED_OUT_EARLIER_KEY] = True
    try:
        if which == "graded":
            choose_report_type(dlg, mr.REPORT_TYPE_FULL)
        dlg._detail_check.setChecked(True)
        qapp.processEvents()
        texts = []
        for for_pdf in (True, False):
            texts += _sentences(_body_text(dlg, for_pdf))
        if which == "saved-earlier":
            from workflow import measurement_messages as M
            body = M.M_REPORT_WORKED_OUT_EARLIER.render()[1]
            assert " ".join(body.split()) in " ".join(texts), (
                "the scene does not show the message it is about")
        bad = _offending(texts)
        assert not bad, "report text naming the app:\n" + "\n".join(
            f"{t[:160]!r} {h}" for t, h in bad)
    finally:
        dlg.close()


def test_a_graph_printed_in_the_pdf_names_no_part_of_the_app():
    """The one empty-graph reason that can reach the PDF: a graph given two
    or more measurements, fewer than two with a value (B8-1084).

    MUTATION, proved to land: "the ticked measurements" back (red)."""
    from ui.dialogs.measurement_report_dialog import _TrendChart
    c = _TrendChart()
    c._metrics = [("m", None, None)]
    c._n_given = 2
    text = c.empty_reason()
    assert not ui_hits(text), (text, ui_hits(text))


#: The same words in German: the controls' German names and the verbs.
UI_WORDS_DE = re.compile(
    r"\b(?:klick\w*|schaltfläche\w*|drück\w*|reiter|registerkarte\w*|"
    r"menü\w*|aufklapp\w*|häkchen|angehakt\w*|anhaken|abgehakt\w*|"
    r"wähle|erneut öffnen)\b"
    r"|„(?:Bericht erzeugen|Aktualisieren|Neu erstellen|Abbrechen)“"
    r"|\b(?:Aktualisieren|Neu erstellen|Grenzwerte bearbeiten)\b",
    re.IGNORECASE)


def test_the_german_report_text_names_no_part_of_the_app():
    """The German of every text above: a translation may not bring back
    what the English leaves out ("angehakt", "Klicke", "Aktualisieren")."""
    import json
    from workflow import measurement_messages as M
    de = json.loads((ROOT / "data" / "i18n" / "de.json").read_text(
        encoding="utf-8"))
    keys = [t for lits in report_function_literals().values() for t in lits]
    keys += _tables()
    for mid in set(report_message_ids()) | \
            messages_the_report_functions_print():
        m = M.CATALOGUE[mid]
        keys += [m.body] + ([m.body_one] if m.body_one else [])
    bad = [(k[:80], UI_WORDS_DE.findall(de[k])) for k in keys
           if k in de and UI_WORDS_DE.search(de[k]) and not _allowed(k)]
    assert not bad, bad


def test_the_pattern_catches_what_it_is_for():
    """The scanner itself: each thing Knut ruled out is found, and printing
    vocabulary is not."""
    for s in ("Update works the report out again.",
              "Click “Generate report” to build it.",
              "Measure its chart on the Measure tab.",
              "put it back and reopen this report",
              "chosen in Edit limits",
              "the ticked measurements"):
        assert ui_hits(s), s
    for s in ("the run of patches a press or a proof is checked on",
              "Updated: 2026-09-25",
              "an update of the paper white",
              "Report Scope", "Judged against: ChromIQ default"):
        assert not ui_hits(s), (s, ui_hits(s))
