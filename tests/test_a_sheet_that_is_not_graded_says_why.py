"""Knut's 12b condition, and the tooltip that did not meet it.

He allowed INFO as the verdict for a profiling run's report on 2026-09-09, on
one condition, in his words:

> It is ok that INFO is shown for measurement report for a profile run, since
> the measurements are not a verification run and will most often not fall
> within set accuracy threshold values. **In this case the report output must
> explain this.**

The explanation was written, and then put in the `title=` attribute of the
Overall cell, which is a HOVER TOOLTIP. An on-screen round drove a real
profiling run and found the sentence in none of the four PDF pages, in English
or in German, and on screen only by hovering four letters. A sentence a reader
cannot read explains nothing.

So this pins the OUTPUT, which is the word he used: the sentence must be in the
rendered report body, and therefore in the saved PDF, not merely in a tooltip.

**AND THE PDF IS ASKED DIRECTLY, because "therefore" is doing too much work.**
Every test here used to stop at `_report_body_html(..., for_pdf=True)`, which
is the HTML handed to `QTextDocument` and not the file anybody reads. This
project has already been bitten by exactly that gap once: the printed help
cards laid out 79 entries and put 29 of them on paper, because pagination
dropped the rest, and no amount of correct HTML would have shown it. The saved
PDF is where the fault this file exists for lived, so the saved PDF is what is
read: `_export_pdf` is driven with the save dialog answered, and the words are
looked for in the text of the pages through `QPdfDocument.getAllText`.
"""
from __future__ import annotations

import html as _html
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.file_manager import Project                     # noqa: E402
from core.settings import AppSettings                     # noqa: E402

from tests.test_report_judging import _colours, _ramp, _write_ti3   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _settings(tmp_path) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return s


def _profiling_run(tmp_path):
    """A run whose measurement is the PROFILING chart, so it is not graded.

    "What a sheet is comes from where it lives" (the design record, section 4):
    a file directly in `runs/runN/` is the run's own profiling chart, printed
    raw by definition, and every row of its report reads INFO.
    """
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    ti3 = run.dir / f"{run.stem}.ti3"
    _write_ti3(ti3, _ramp(16) + _colours(), verification=False)
    return proj, run, ti3


def _dialog(s, ti3):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    return MeasurementReportDialog(s, None, initial_ti3=ti3)


#: The words that carry his condition. Not the whole sentence, so a reword that
#: keeps the meaning does not fail this, and a deletion does.
_MUST_SAY = ("not graded", "build a profile", "outside the accuracy limits")


def _saved_pdf_text(dlg, path, monkeypatch) -> str:
    """Save the report as a PDF the way the button does, and read it back.

    The save dialog is answered instead of shown, and the "open it when it is
    written" step is stubbed, so no viewer is launched by a test run.
    """
    import ui.widgets as W
    from PyQt6.QtGui import QDesktopServices
    from PyQt6.QtPdf import QPdfDocument

    monkeypatch.setattr(W, "save_file_dialog", lambda *a, **k: str(path))
    monkeypatch.setattr(QDesktopServices, "openUrl",
                        staticmethod(lambda *a, **k: True))
    dlg._export_pdf()
    assert path.is_file(), "no PDF was written at all"
    doc = QPdfDocument(None)
    doc.load(str(path))
    pages = doc.pageCount()
    assert pages >= 1, "the PDF has no pages"
    # Every page, so a sentence pushed off the end by pagination is missing
    # here and not merely somewhere else.
    return " ".join(doc.getAllText(i).text() for i in range(pages))


def test_the_explanation_is_in_the_report_body_and_not_only_a_tooltip(qapp, tmp_path):
    proj, run, ti3 = _profiling_run(tmp_path)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        runs = dlg._runs_for_report()
        assert runs, "the profiling measurement produced no report column"
        body = dlg._report_body_html(runs, for_pdf=True)

        # Strip every tag, which is what removes the `title=` attribute the
        # sentence used to hide in. What is left is what a reader sees.
        import re
        visible = _html.unescape(re.sub(r"<[^>]+>", " ", body))

        for phrase in _MUST_SAY:
            assert phrase in visible, (
                f"the report output never says {phrase!r}. Knut's condition for "
                "allowing INFO on a profiling run was that the report output "
                "explains it; a tooltip is not output.")
    finally:
        dlg.deleteLater()


def test_the_explanation_reaches_the_saved_pdf(qapp, tmp_path, monkeypatch):
    """The same condition, asked of the file a reader is handed.

    Correct HTML is not a printed page. This is the step the tests above do not
    cover and the one the fault was reported on.
    """
    proj, run, ti3 = _profiling_run(tmp_path)
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        text = _saved_pdf_text(dlg, tmp_path / "report.pdf", monkeypatch)
        for phrase in _MUST_SAY:
            assert phrase in text, (
                f"the SAVED PDF never says {phrase!r}. It is in the report "
                "body, so this is pagination or painting losing it, which is "
                "invisible to every test that stops at the HTML.")
    finally:
        dlg.deleteLater()


def test_a_graded_sheet_does_not_carry_the_explanation(qapp, tmp_path):
    """The other half, or the test above passes on a note printed always.

    A verification IS graded, so the sentence would be a lie on its report.
    """
    from tests.test_report_window_limit_controls import _verified_run
    proj, run, ti3s = _verified_run(tmp_path, dates=1)
    dlg = _dialog(_settings(tmp_path), ti3s[-1])
    try:
        import re
        body = dlg._report_body_html(dlg._runs_for_report(), for_pdf=True)
        visible = _html.unescape(re.sub(r"<[^>]+>", " ", body))
        assert "build a profile rather than to check one" not in visible
    finally:
        dlg.deleteLater()


def test_the_explanation_survives_a_standard_named_set(qapp, tmp_path,
                                                       monkeypatch):
    """A challenge round found this silently un-fixed by a later change.

    The footnote is selected by EXACT EQUALITY on the column's reason. A fix
    that appended a caveat to that reason made the equality fail, so the
    explanation was dropped for every standard-named set while still printing
    for ChromIQ's own. Three identical saved profiling reports differed only in
    which set they named, and only one of the three explained itself.
    """
    import re
    from workflow import measurement_report as mr
    from workflow import run_compliance as rc

    for set_id, label in (("chromiq_default", "ChromIQ default (recommended)"),
                          ("custom_iso_12647_7", "Custom ISO 12647-7"),
                          ("iso_12647_7", "ISO 12647-7:2016 values")):
        proj, run, ti3 = _profiling_run(tmp_path / set_id)
        rep = mr.build_report(ti3)
        mr.stamp_verdict(rep, rc.run_limits(run, {}).limits,
                         set_id=set_id, set_label=label)
        mr.save_report(rep, ti3.parent)
        dlg = _dialog(_settings(tmp_path / set_id), ti3)
        try:
            body = dlg._report_body_html(dlg._runs_for_report(), for_pdf=True)
            visible = _html.unescape(re.sub(r"<[^>]+>", " ", body))
            assert "build a profile" in visible, (
                f"the ungraded explanation is missing when the set is {label!r}")
            # …and in the file, per set. "Three identical saved profiling
            # reports" is what the challenge round compared, and saved is the
            # word that matters.
            text = _saved_pdf_text(dlg, tmp_path / f"{set_id}.pdf", monkeypatch)
            assert "build a profile" in text, (
                f"the SAVED PDF loses the ungraded explanation when the set is "
                f"{label!r}, though the report body carries it")
        finally:
            dlg.deleteLater()
