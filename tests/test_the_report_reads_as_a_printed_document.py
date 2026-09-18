"""The Measurement Report is a document, not a description of a window.

Knut, beta 20 (#182): *"the text must be written as if it is a separate
document printed for a customer, and that customer knows nothing of the
Measurement Report windows, buttons, selections that can be made or changed ...
shall only contain data and results relating to that one reports settings, and
not show information that other reports exist with other 'judged against'
threshold sets."*

Two rules come out of that, and this file is both of them:

* the rendered body may not borrow the WINDOW's vocabulary (a list above, a
  tick, a pulldown, a menu path, a hover), because none of it exists on paper;
* it may not mention that other reports, or other limit sets, exist.

The body is rendered from a real dialog on a real project, twice: the one-page
summary and the full colour check, with a second run bound to a different limit
set so the "other set" paragraph would fire if it were still there.
"""
from __future__ import annotations

import re

import pytest
from PyQt6.QtWidgets import QApplication

#: Phrases that describe the WINDOW. Each one was in the document on
#: 2026-09-17 and each is invisible to someone holding a printed sheet.
WINDOW_WORDS = (
    "in the list above",
    "loaded in this window",
    "chosen in this window",
    "unticked",
    "ticked in Preferences",
    "point at the cell",
    "Check & Refine",
    "pulldown",
    "click",
    "button",
)

#: Phrases that tell the reader about OTHER reports or OTHER limit sets.
OTHER_REPORT_WORDS = (
    "judged against a different limit set",
    "not in the results below",
    "were not all judged against the same limit set",
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _plain(html_text: str) -> str:
    """The text a reader sees, tags and entities out of the way."""
    from PyQt6.QtGui import QTextDocument
    doc = QTextDocument()
    doc.setHtml(html_text)
    return doc.toPlainText()


def _bodies(tmp_path, qapp) -> list:
    """The rendered body of every report type this window can produce."""
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from workflow.run_compliance import bind_run
    dlg, _run, fm = _dialog(tmp_path, qapp)
    out = []
    try:
        # a second run on ANOTHER limit set, which is the state that used to
        # print a red paragraph naming it
        run2 = fm.project().new_run()
        v2 = run2.new_verification()
        v2.ensure_dir()
        v2.measurement_ti3.write_text(
            _cgats("CTI3", [(r * 0.5, g, b) for (r, g, b) in _PATCHES]),
            encoding="utf-8")
        bind_run(run2, "chromiq_tight", None)
        dlg._add_source(v2.measurement_ti3)
        qapp.processEvents()
        for i in range(dlg._type_combo.count()):
            dlg._type_combo.setCurrentIndex(i)
            qapp.processEvents()
            label = dlg._type_combo.itemText(i)
            out.append((label, _plain(dlg._report_body_html(
                dlg._runs_for_report(), for_pdf=False))))
    finally:
        dlg.close()
    return out


def test_no_report_type_describes_the_window(tmp_path, qapp):
    """MUTATION: put "in the list above" back into `_scope_html` and this goes
    red on every report type."""
    for label, body in _bodies(tmp_path, qapp):
        low = body.lower()
        for phrase in WINDOW_WORDS:
            assert phrase.lower() not in low, (
                f"the {label!r} report says {phrase!r}, which a printed sheet "
                f"cannot show its reader")


def test_no_report_type_mentions_another_report_or_another_limit_set(tmp_path,
                                                                     qapp):
    """MUTATION: restore the `_other_limit_sets_html` block and this goes
    red."""
    for label, body in _bodies(tmp_path, qapp):
        for phrase in OTHER_REPORT_WORDS:
            assert phrase not in body, (
                f"the {label!r} report tells its reader that other reports "
                f"exist: {phrase!r}")


def test_a_filtered_report_still_says_it_is_filtered(tmp_path, qapp):
    """Sebastian's honesty rule survives the rewrite, by count.

    MUTATION: drop the "covers N of the M" note and this goes red.
    """
    bodies = _bodies(tmp_path, qapp)
    assert bodies
    hits = [b for _l, b in bodies
            if re.search(r"covers \d+ of the \d+ measurements", b)]
    assert hits, (
        "a report that leaves measurements out says nothing about it at all")
