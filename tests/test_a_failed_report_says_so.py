"""A measurement report that could not be saved says so ON SCREEN.

`TabMeasure._maybe_save_measurement_report` runs after every measurement when
Preferences ▸ Reports has "Save measurement report" on, which it does by
default. It ended in::

    except Exception as exc:            # noqa: BLE001
        log.warning("measurement report failed: %s", exc)

— and nothing else. The measurement completed, the window looked exactly as it
does on a good run, and the only evidence was a line in a log file the user
never opens.

**The silence was worse than an omission.** The SUCCESS of the same operation
announces itself in the measurement log ("[Report] Measurement report saved:
…"), so the window that had just written no report was indistinguishable from
the window that had. A failure that looks like a success is not a missing
message; it is a wrong one.

These tests drive the real tab and the real failure — a `build_report` that
raises, and a `reports/` folder that cannot be written — and assert that the
user is told, in the two places this tab already speaks: its log and its status
line. `tests/test_message_catalogue.py` separately pins that the words are
M-REPORT-NOT-SAVED's and not this method's own.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.argyll_runner import ArgyllRunner               # noqa: E402
from core.file_manager import FileManager, Project        # noqa: E402
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from workflow import measurement_messages as M            # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    s.set("save_measurement_report", True)
    fm = FileManager(s)
    Project.create(tmp_path / "P", "P").current_run().ensure_dir()
    fm.set_target_name("P")
    from ui.tabs.tab_measure import TabMeasure
    t = TabMeasure(ArgyllRunner(s), s)
    t.set_target_controller(MeasurementTargetController(fm))
    yield t
    t.deleteLater()


def _a_ti3(tmp_path: Path) -> Path:
    """A file with the right name and suffix — the content never matters here,
    because every test in this file makes the report fail before it is read."""
    p = tmp_path / "run" / "c.ti3"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("CTI3\n", encoding="utf-8")
    return p


def _log_text(tab) -> str:
    return tab._log.toPlainText()


# --------------------------------------------------------------------------
# The report failed
# --------------------------------------------------------------------------
def test_a_report_that_cannot_be_built_is_reported_on_screen(tab, tmp_path,
                                                             monkeypatch):
    """THE GUARD. Remove the on-screen path and this test is the one that
    fails."""
    import workflow.measurement_report as mr

    def boom(*a, **kw):
        raise OSError("No space left on device")

    monkeypatch.setattr(mr, "build_report", boom)
    tab._maybe_save_measurement_report(_a_ti3(tmp_path))

    text = _log_text(tab)
    headline, _body = M.M_REPORT_NOT_SAVED.render()
    assert headline in text, f"nothing on screen said the report failed:\n{text!r}"
    # …and the technical line the message points at, on the line below it, so
    # somebody who wants to look into it does not have to go and find a file.
    assert "No space left on device" in text


def test_a_report_that_cannot_be_written_is_reported_on_screen(tab, tmp_path,
                                                               monkeypatch):
    """The other half: the report built fine and the WRITE failed."""
    import workflow.measurement_report as mr
    monkeypatch.setattr(mr, "build_report", lambda *a, **kw: {"created": "t"})

    def cannot_write(*a, **kw):
        raise PermissionError("Permission denied: reports/")

    monkeypatch.setattr(mr, "save_report", cannot_write)
    tab._maybe_save_measurement_report(_a_ti3(tmp_path))

    headline, _ = M.M_REPORT_NOT_SAVED.render()
    assert headline in _log_text(tab)
    assert "Permission denied" in _log_text(tab)


def test_the_status_line_says_it_too(tab, tmp_path, monkeypatch):
    """The log can be collapsed; the status line under the buttons cannot.
    Both, for the same reason `_on_cr30_dropped_reading` uses both."""
    import workflow.measurement_report as mr
    monkeypatch.setattr(
        mr, "build_report",
        lambda *a, **kw: (_ for _ in ()).throw(OSError("disk gone")))
    tab._maybe_save_measurement_report(_a_ti3(tmp_path))

    headline, _ = M.M_REPORT_NOT_SAVED.render()
    # `isVisible()` is False for every child of a tab nobody has shown, so ask
    # the question the flash actually answers: is the label switched ON inside
    # its own parent? A test that asked the other question would pass on an
    # empty label for ever.
    assert tab._status_bar_lbl.isVisibleTo(tab._status_bar_lbl.parentWidget())
    assert headline in tab._status_bar_lbl.text()


def test_the_whole_body_reaches_the_user_not_just_the_headline(tab, tmp_path,
                                                               monkeypatch):
    """The headline says WHAT; the body says what it costs and what to do.
    A headline alone would be the same silence with a title on it."""
    import workflow.measurement_report as mr
    monkeypatch.setattr(
        mr, "build_report",
        lambda *a, **kw: (_ for _ in ()).throw(OSError("nope")))
    tab._maybe_save_measurement_report(_a_ti3(tmp_path))

    _headline, body = M.M_REPORT_NOT_SAVED.render()
    assert body in _log_text(tab)


def test_an_exception_with_no_message_still_names_something(tab, tmp_path,
                                                            monkeypatch):
    """`str(exc)` is empty for a bare `RuntimeError()`, and a technical line
    ending in a colon with nothing after it says less than the log line it
    replaced."""
    import workflow.measurement_report as mr
    monkeypatch.setattr(
        mr, "build_report",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError()))
    tab._maybe_save_measurement_report(_a_ti3(tmp_path))

    line = [ln for ln in _log_text(tab).splitlines()
            if "Technical detail" in ln]
    assert line and line[0].rstrip().endswith("RuntimeError"), line


# --------------------------------------------------------------------------
# Basti's standing rule: "friendly, extensive, easy to understand and correct"
# --------------------------------------------------------------------------
def test_the_message_says_first_what_was_not_lost(tab, tmp_path, monkeypatch):
    """The most valuable sentence in the message. A user who reads "the report
    failed" and concludes their MEASUREMENT is gone has been badly served by a
    technically accurate sentence — so the reassurance comes first, before the
    message says what did go wrong."""
    _headline, body = M.M_REPORT_NOT_SAVED.render()
    first = body.split("\n\n")[0].lower()
    assert "measurement is safe" in first
    assert "nothing about it has changed" in first


def test_the_message_carries_no_exception_text_of_its_own():
    """No stack trace, no errno, no exception class name in the prose. The
    technical detail is a LOG LINE, named as such, and the message points at
    it — it is not the explanation."""
    _headline, body = M.M_REPORT_NOT_SAVED.render()
    assert "{" not in body and "}" not in body, \
        "the message interpolates something; it must carry no placeholder"
    for smell in ("Errno", "Error:", "Exception", "Traceback", "errno"):
        assert smell not in body, f"the message shows {smell!r} to a user"


def test_the_message_claims_no_cause_it_cannot_know(tab, tmp_path, monkeypatch):
    """The same `except` catches a failure to BUILD the report and a failure to
    WRITE it, so the message may not assert either. It offers the usual reasons
    as things to CHECK, which is the honest form of the same help."""
    _headline, body = M.M_REPORT_NOT_SAVED.render()
    assert "usual reasons" in body
    # …and it tells the user where the specific answer is.
    assert "technical detail" in body.lower()


def test_the_message_says_what_to_do_and_that_nothing_needs_redoing():
    _headline, body = M.M_REPORT_NOT_SAVED.render()
    assert "do not need to measure anything again" in body
    assert "Measurement report button" in body
    assert "Preferences" in body


def test_the_message_is_approved_and_the_ruling_is_recorded():
    """Basti ruled on 2026-09-04 — *"i approve it"* — after reading the text in
    full and asking whether it was "friendly, extensive, easy to understand".

    This test used to pin the OPPOSITE, that the message was still awaiting a
    ruling, and it is kept rather than deleted because the pair is the point: a
    message may not become approved by drifting there. It was unapproved, a
    person said so in as many words, and the flag, the catalogue section and
    this guard moved together in one change. If the flag is ever flipped without
    the ruling being recorded beside it in the model, the other half of this
    fails."""
    assert M.M_REPORT_NOT_SAVED.approved is True
    assert "M-REPORT-NOT-SAVED" not in M.PROPOSED


# --------------------------------------------------------------------------
# …and the good path is unchanged
# --------------------------------------------------------------------------
def test_a_report_that_saves_says_only_that(tab, tmp_path, monkeypatch):
    """The failure message must not appear on a run that worked — which is the
    mirror of the fault, and the way a well-meant warning becomes noise."""
    import workflow.measurement_report as mr
    monkeypatch.setattr(mr, "build_report", lambda *a, **kw: {"created": "t"})
    saved = tmp_path / "run" / "reports" / "report_x.json"

    def ok(report, run_dir):
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_text("{}", encoding="utf-8")
        return saved

    monkeypatch.setattr(mr, "save_report", ok)
    tab._maybe_save_measurement_report(_a_ti3(tmp_path))

    headline, _ = M.M_REPORT_NOT_SAVED.render()
    text = _log_text(tab)
    assert headline not in text
    assert "report_x.json" in text


def test_the_option_being_off_is_still_silent(tab, tmp_path, monkeypatch):
    """A user who switched the report off is not told about a report."""
    tab._settings.set("save_measurement_report", False)
    import workflow.measurement_report as mr
    monkeypatch.setattr(
        mr, "build_report",
        lambda *a, **kw: (_ for _ in ()).throw(OSError("never reached")))
    tab._maybe_save_measurement_report(_a_ti3(tmp_path))
    assert _log_text(tab).strip() == ""


# --------------------------------------------------------------------------
# The log line the fault was hiding in is still there
# --------------------------------------------------------------------------
def test_the_python_log_line_was_not_traded_away(tab, tmp_path, monkeypatch,
                                                 caplog):
    """The on-screen path is an ADDITION. A support log that stopped recording
    the exception would have traded one blindness for another."""
    import logging

    import workflow.measurement_report as mr
    monkeypatch.setattr(
        mr, "build_report",
        lambda *a, **kw: (_ for _ in ()).throw(OSError("still logged")))
    with caplog.at_level(logging.WARNING):
        tab._maybe_save_measurement_report(_a_ti3(tmp_path))
    assert any("still logged" in r.getMessage() for r in caplog.records)
