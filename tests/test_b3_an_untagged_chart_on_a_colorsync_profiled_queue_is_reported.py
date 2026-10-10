"""B3, 2026-10-10 (Knut's HP CLJ5550 on a generic PostScript queue, with his
own profile assigned to the printer in ColorSync Utility).

The macOS dialog route gives the chart the profile macOS converts the job
into (its output intent), so the conversion is the identity. Measured on a
capture queue set up like Knut's
(~/Desktop/ChromIQ-work/2026-10-10_434b1_B3/runs/): with the tag, the job's
page image equals the chart's pixels exactly (1,372,807 of 1,372,807); with
the tag withheld, macOS changed them by 18.6 levels on average (max 107).

When the chart could NOT be given that profile, the read-back said so only
for a PPD that declares `*cupsICCProfile`. A generic PostScript PPD declares
none, so the status line said "application colour matching" and nothing else
over a converted chart. The output intent itself is now the condition.
"""
from __future__ import annotations

import pytest

from workflow import native_print_macos as npm
from workflow import print_ticket as pt

GENERIC_PS = '*ModelName: "Generic PostScript Printer"\n*ColorDevice: True\n'


@pytest.fixture
def no_cups(monkeypatch, tmp_path):
    ppd = tmp_path / "q.ppd"
    ppd.write_text(GENERIC_PS)
    from workflow.print_manager import PrintModule
    monkeypatch.setattr(PrintModule, "find_ppd_path", staticmethod(lambda q: str(ppd)))
    monkeypatch.setattr(npm, "_queue_name", lambda d: "HP_CLJ5550_PostScript")
    monkeypatch.setattr(pt, "find_job", lambda q, since: 50)
    monkeypatch.setattr(
        pt, "check_job",
        lambda q, job, exp, ppd_text=None, tagged_with=None, tagged_icc=None:
        pt.TicketReport(queue=q, job_id=job, read=True, expected=dict(exp),
                        tagged_with=tagged_with))


def _sub(tagged: bytes, intent):
    return npm.Submission("HP CLJ5550-PostScript", dict(npm._LOCKED_COLOR_SETTINGS),
                          0.0, tagged, "Knut 2026.02.09" if tagged else None,
                          output_intent=intent)


def test_untagged_with_an_output_intent_is_reported(no_cups):
    """MUTATION: drop `sub.output_intent` from the condition in `read_back`
    and this goes red (the generic PPD names no profile)."""
    rep = npm.read_back(_sub(b"", "Knut 2026.02.09"))
    assert rep.tag_matches_job is False
    assert not rep.ok                     # -> M-PRINT-JOB-UNTAGGED on screen


def test_tagged_with_it_stays_quiet(no_cups):
    rep = npm.read_back(_sub(b"icc", "Knut 2026.02.09"))
    assert rep.tag_matches_job is None and rep.ok


def test_no_output_intent_and_no_ppd_profile_stays_quiet(no_cups):
    """The beta 15 rule for a printer with no profile anywhere is unchanged."""
    rep = npm.read_back(_sub(b"", None))
    assert rep.tag_matches_job is None and rep.ok


def test_print_frames_records_the_intent_even_when_the_tag_fails():
    import inspect
    src = inspect.getsource(npm.print_frames)
    assert "output_intent = dest_name if dest_icc else None" in src
    assert "output_intent=output_intent" in src
    # recorded BEFORE the failure branch clears dest_name
    assert src.index("output_intent = dest_name") < src.index("dest_icc, dest_name = None, None")


# ---- the confirmation window named the paper twice --------------------------
# Knut's screenshot (#182 6095262115): "Media Size: A4" (the driver's option)
# and, three rows lower, "Media size: 210 × 297 mm" (ChromIQ's own page).
class _Combo:
    def __init__(self, data, text):
        self._d, self._t = data, text

    def currentData(self):
        return self._d

    def currentText(self):
        return self._t


def _rows_of_the_window(monkeypatch, combos, labels):
    from ui.tabs import tab_print as tp
    seen = {}

    class _Dlg:
        def __init__(self, rows, warnings, n, parent):
            seen["rows"] = rows

        def exec(self):
            return 0

        def dont_ask_again(self):
            return False

    monkeypatch.setattr(tp, "PreflightDialog", _Dlg)
    tab = tp.TabPrint.__new__(tp.TabPrint)
    tab._option_combos = combos
    tab._option_label_for = lambda name: labels[name]
    tab._colour_rows = lambda printer, opts, tiff: [("Colour management", "Off (forced)")]
    tp.TabPrint._show_preflight(tab, "HP", {}, 0, (595.44, 842.04), None, 1)
    return seen["rows"]


def test_the_paper_is_named_once_with_its_millimetres(monkeypatch):
    """MUTATION: append the "Media size" row unconditionally again and this
    goes red."""
    rows = _rows_of_the_window(
        monkeypatch,
        {"InputSlot": _Combo("", "Printer Default"), "PageSize": _Combo("A4", "A4")},
        {"InputSlot": "Media Source", "PageSize": "Media Size"})
    names = [n for n, _v in rows]
    assert names.count("Media Size") == 1 and "Media size" not in names
    assert ("Media Size", "A4 (210 × 297 mm)") in rows


def test_a_queue_without_a_size_option_keeps_the_millimetre_row(monkeypatch):
    rows = _rows_of_the_window(monkeypatch, {}, {})
    assert ("Media size", "210 × 297 mm") in rows
