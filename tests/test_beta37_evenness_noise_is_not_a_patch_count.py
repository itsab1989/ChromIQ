"""A sheet too noisy to judge evenness is told so (beta 37, A-F3 = B-H2, B-M7).

Round A F3 and round B H2: on the evenness demo's noisy date the N-A note read
"the measured chart has 42 patches in the emptiest ninth of the page, too few
for this row", while the notes beside it judged the same chart's 42-patch
areas on the other three dates. The cause is the measurement's noise, and the
window's strip then offered "what to add to the chart" for it. Round B M7:
under a list holding only the evenness rows, the strip's tail sent the reader
to a "Neutral grey ramp" with 16 steps.
"""
from __future__ import annotations

import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_beta37_round_fixes import _settings, _visible   # noqa: E402

_EVEN_ROWS = ("uniformity_sd", "uniformity_de00_max_from_mean")


def _dialog(tmp_path, sigma=2.5, pages=(12,)):
    from tests.test_evenness_across_the_sheet import (_even, _write_chart,
                                                      _write_sheet)
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    ti2, where = _write_chart(tmp_path / "c", pages=pages)
    t3 = _write_sheet(ti2, where, _even(sigma))
    return MeasurementReportDialog(_settings(tmp_path), None, initial_ti3=t3)


def test_the_noise_note_names_the_noise_and_the_limit_and_no_patch_count(
        qapp, tmp_path):
    """MUTATION (proved red 2026-09-23): put the old sentence back in
    `_evenness_noise_sentence` ("the measured chart has {n} patches in the
    emptiest ninth of the page, too few for this row: ..."); this goes red on
    "too noisy" and on the patch count."""
    dlg = _dialog(tmp_path)
    try:
        text = _visible(dlg)
        # THE NOTES UNDER THE RESULTS GRID. Since G12 (beta 39) the detailed
        # table lists the notes it points at as well, with the same numbers,
        # so the whole body carries each sentence twice when "Show detailed
        # data" is on; the count below is of the list under the grid.
        text = text.split("Detailed data per measurement")[0]
        notes = [s for s in re.split(r"\s\d+\)\s", text)
                 if "noise here is" in s]
        assert len(notes) == 2, "one note per evenness row withheld"
        for n in notes:
            assert "too noisy" in n, n
            assert "emptiest ninth" not in n and "too few" not in n, n
            assert "patches in" not in n, n
        # each note names the limit of ITS row: 1.50 and 1.00 under ChromIQ
        # default (Knut's ruling 4)
        joined = " ".join(notes)
        assert "limit of 1.50" in joined and "limit of 1.00" in joined, joined
    finally:
        dlg.deleteLater()


def test_the_strip_does_not_offer_a_chart_change_for_the_noise(qapp, tmp_path):
    """MUTATION (proved red 2026-09-23): drop the `EVENNESS_NOISE_REASONS`
    filter from `_mismatch_text`; the evenness rows come back on the strip."""
    from workflow.compliance_sets import N_A
    dlg = _dialog(tmp_path)
    try:
        rows, _rec = dlg._verdict_rows(dlg._report)
        ev = [x for x in rows if x.get("row_id") in _EVEN_ROWS]
        assert ev and all(x["word"] == N_A for x in ev)
        assert "Evenness" not in dlg._mismatch_text()
    finally:
        dlg.deleteLater()


def test_a_strip_about_evenness_alone_names_the_layout_not_the_grey_ramp(
        qapp, tmp_path, monkeypatch):
    """MUTATION (proved red 2026-09-23): always render
    `M_REPORT_CHART_MISMATCH` in `_mismatch_text`; the grey ramp is back."""
    from workflow.compliance_sets import N_A
    from workflow.measurement_report import REASON_EVENNESS_GRID_TOO_SMALL
    dlg = _dialog(tmp_path, sigma=0.2)
    try:
        only = [{"row_id": rid, "key": rid, "word": N_A, "value": None,
                 "threshold": 1.5, "reason": REASON_EVENNESS_GRID_TOO_SMALL}
                for rid in _EVEN_ROWS]
        monkeypatch.setattr(type(dlg), "_verdict_rows",
                            lambda self, r: ([dict(x) for x in only], False))
        text = dlg._mismatch_text()
        assert "Evenness" in text
        assert "grey ramp" not in text and "Create Chart" not in text, text
        assert "strips and more rows on a page" in text
        # ...and a list with a grey row in it keeps the general closing
        mixed = only + [{"row_id": "grey_balance_neutral_ramp_avg",
                         "key": "grey_balance_neutral_ramp_avg", "word": N_A,
                         "value": None, "threshold": 1.5,
                         "reason": "too_few_steps"}]
        monkeypatch.setattr(type(dlg), "_verdict_rows",
                            lambda self, r: ([dict(x) for x in mixed], False))
        assert "Neutral grey ramp" in dlg._mismatch_text()
    finally:
        dlg.deleteLater()
