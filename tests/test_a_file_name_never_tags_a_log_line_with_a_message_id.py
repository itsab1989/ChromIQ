"""A message is recognised in the app log by its own words, never by a value.

4.3.58, seen in a tester's log: the app log tags a panel line or a window with
the §M id of a message rendered shortly before when "the first 60 characters
of the body" occur in it (`core.question_log.panel_line`, `message_id_of`).
M-IMPORT-CXF-CONDITION's body begins with the file's name ("{name} holds the
readings of every patch more than once ..."), and with a name of 60
characters or more those 60 characters were the name alone, so every later,
unrelated line naming that file was tagged M-IMPORT-CXF-CONDITION. Users see
nothing of this; it misled the reader of the log.

The probe is now the template's first literal run of text.
"""
from __future__ import annotations

import logging

import pytest

LONG_NAME = ("Glossy-Baryta-Paper-ET8550-PK-2026-11-22-run3-dual-scan-M0-M1-M2"
             "-final-retry.mxf")


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    from core import question_log as ql
    monkeypatch.setattr(ql, "_PANEL_COUNT", {})
    monkeypatch.setattr(ql, "_RENDERED", type(ql._RENDERED)())


def _panel_ids(caplog):
    out = []
    for r in caplog.records:
        m = r.getMessage()
        if m.startswith("panel:"):
            out.append(m.split(" id=", 1)[1].split(" ", 1)[0] if " id=" in m else "")
    return out


def _render():
    from workflow import measurement_messages as M
    assert len(LONG_NAME) > 60
    return M.M_IMPORT_CXF_CONDITION.render(name=LONG_NAME,
                                           conditions="M0, M1 and M2")


def test_a_later_line_naming_the_file_is_not_tagged(caplog):
    from core import question_log as ql
    _render()
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        ql.panel_line("measure", f"Imported {LONG_NAME}: 1012 patches, M1")
        ql.panel_line("measure", f"Converting {LONG_NAME} to a .ti3 file")
    assert _panel_ids(caplog) == ["", ""], (
        "a line that only names the file was tagged with the message's id")


def test_the_message_itself_is_still_tagged(caplog):
    from core import question_log as ql
    _title, body = _render()
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        ql.panel_line("measure", body)
    assert _panel_ids(caplog) == ["M-IMPORT-CXF-CONDITION"]


def test_a_window_naming_the_file_is_not_this_message(qapp):
    from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout
    from core import question_log as ql
    _render()
    other = QDialog()
    QVBoxLayout(other).addWidget(QLabel(f"{LONG_NAME} was imported."))
    own = QDialog()
    own.setWindowTitle("ChromIQ")
    _t, body = _render()
    QVBoxLayout(own).addWidget(QLabel(body))
    try:
        assert ql.message_id_of(other) == ""
        assert ql.message_id_of(own) == "M-IMPORT-CXF-CONDITION"
    finally:
        other.deleteLater()
        own.deleteLater()


def test_the_probe_is_the_templates_own_words():
    from core import question_log as ql
    assert ql._probe("x", "{name} holds the readings of every patch") == \
        "holds the readings of every patch"
    assert ql._probe("x", "{reason}") == ""
    assert ql._probe("x", "{a} {b}") == ""
    # without a template (an old caller) it is the shown text, as before
    assert ql._probe("Shown text here", None) == "Shown text here"


# 4.3.59 review: two messages have no literal run of 20 characters, so the
# 20-character rule alone left them untagged. They fall back to their longest
# run of at least 10 characters, still the template's own words.
def test_a_message_without_a_long_run_falls_back_to_its_longest_run():
    from core import question_log as ql
    from workflow import measurement_messages as M
    assert ql._probe("x", M.M_DUAL_PASS_TOO_FAST_LINE.body) == "seconds of reading."
    assert ql._probe("x", M.M_REPORT_RAW_JUDGED_AGAINST.body) == "(printed raw)"
    # a run under 10 characters is no probe: too common to name one message
    assert ql._probe("x", "{a} is short {b}") == ""
    # the first run of 20 still wins over a longer later one
    assert ql._probe("x", "{a} twenty characters ok {b} and then a much longer run here") \
        == "twenty characters ok"


@pytest.mark.parametrize("msg, kw", [
    ("M_DUAL_PASS_TOO_FAST_LINE", dict(fewest=3, need=5, uv_s="2.4")),
    ("M_REPORT_RAW_JUDGED_AGAINST", dict(set="Strict")),
])
def test_the_two_short_run_messages_are_tagged_again(caplog, msg, kw):
    from core import question_log as ql
    from workflow import measurement_messages as M
    m = getattr(M, msg)
    _title, body = m.render(**kw)
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        ql.panel_line("measure", body)
    assert _panel_ids(caplog) == [m.id]


def test_the_fallback_never_takes_a_long_file_name(caplog):
    """A short-run message filled with a long file name: a later line naming
    only that file is not tagged."""
    from core import question_log as ql
    from workflow import measurement_messages as M
    M.M_REPORT_RAW_JUDGED_AGAINST.render(set=LONG_NAME)
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        ql.panel_line("measure", f"Imported {LONG_NAME}: 1012 patches, M1")
    assert _panel_ids(caplog) == [""]
