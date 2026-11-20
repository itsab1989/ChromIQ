"""4.3.52 fix round, MUST-2 of the independent safety review: the one-time migration of the old
"Don't ask after each step".

4.3.50 / 4.3.51's OFF dropped only the report after each step; 4.3.52's OFF is far more
automatic. A choice given for the old meaning is not consent to the new one: when the new
consent (version 4) is given for the first time, the guidance is switched ON, whatever the old
value was, and the consent page says so ("This is switched on now, also if you had switched off
the earlier question. You can switch it off in Preferences > Beta or below."). After that the
person's choice is theirs. Tested with a settings file as 4.3.50 writes it (consent 3, the old
tick off, and on) and with a fresh install."""
from __future__ import annotations

import logging

import pytest
from PyQt6.QtCore import QSettings

from core.i18n import tr
from tests.i1io_table.test_job_reading import small_sheet
from tests.i1io_table.test_window import ARGS, project
from tests.i1io_table.window_person import WindowPerson
from tests.i1io_table.window_sim import WindowSim
from ui import i1io_table_window as W
from workflow import measurement_messages as M

SENTENCE = ("This is switched on now, also if you had switched off the earlier question. You can "
            "switch it off in Preferences > Beta or below.")


def _settings_file(tmp_path, text: "str | None"):
    """An AppSettings on an .ini file with *text* as its content (None: a fresh install, no
    file)."""
    from core.settings import AppSettings
    path = tmp_path / "ChromIQ.ini"
    if text is not None:
        path.write_text(text, encoding="utf-8")
    s = AppSettings()
    s._qs = QSettings(str(path), QSettings.Format.IniFormat)
    s.set(W.CAL_KEY, "table tile")
    return s


#: what 4.3.50 writes after the consent of version 3 and the done page's old tick
INI_4350_OFF = ("[General]\ni1io_table_consent_given=3\ni1io_table_ask_after_each_step=false\n"
                "i1io_support_beta=true\n")
INI_4350_ON = ("[General]\ni1io_table_consent_given=3\ni1io_table_ask_after_each_step=true\n"
               "i1io_support_beta=true\n")


def _start(qtbot, monkeypatch, tmp_path, s):
    sim = WindowSim()
    monkeypatch.setattr(W, "JOB_FACTORY", sim.factory)
    monkeypatch.setattr(W, "USB_STATUS", lambda: (True, ""))
    _proj, run = project(tmp_path, small_sheet())
    win = W.TableMeasureWindow(None, s, small_sheet(), run, ARGS)
    qtbot.addWidget(win)
    win.show()
    win.start()
    p = WindowPerson(win, sim, lambda c: qtbot.waitUntil(c, timeout=15000))
    return win, sim, p


@pytest.mark.parametrize("ini,was", [(INI_4350_OFF, False), (INI_4350_ON, True), (None, True)],
                         ids=["4350-old-tick-off", "4350-old-tick-on", "fresh-install"])
def test_must2_the_consent_switches_the_guidance_on_once(qtbot, monkeypatch, tmp_path, ini, was,
                                                         caplog):
    s = _settings_file(tmp_path, ini)
    assert W.guided(s) is was                       # the stored value is read as it was
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        win, sim, p = _start(qtbot, monkeypatch, tmp_path, s)
        assert p.page() == "consent"
        # the page says what is true for everybody, and shows the guidance on
        assert tr(SENTENCE) in win._text.text()
        assert tr("This is switched on at first") not in win._text.text()
        assert len(win._tick_widgets) == 2 and win._tick_widgets[1].isChecked()
        win._tick_widgets[0].setChecked(True)
        p.press("I understand, drive my table")
        assert W.guided(s) is True and W.consent_given(s)
        assert sim.jobs and sim.jobs[0].guided is True
        # the guided START: the first page is shown
        assert p.page() == "prepare", p.page()
    msgs = [r.getMessage() for r in caplog.records if r.name == "chromiq.events"]
    lines = [m for m in msgs if m.startswith("table guidance:") and "consent_page" in m]
    assert lines and "now=on" in lines[0] and f"was={'on' if was else 'off'}" in lines[0], lines
    # stored in the file itself, as the next START reads it
    s._qs.sync()
    assert QSettings(str(tmp_path / "ChromIQ.ini"), QSettings.Format.IniFormat).value(
        W.ASK_KEY) in (True, "true")


def test_must2_unticked_on_the_consent_page_is_the_persons_own_choice(qtbot, monkeypatch,
                                                                      tmp_path):
    s = _settings_file(tmp_path, INI_4350_OFF)
    win, sim, p = _start(qtbot, monkeypatch, tmp_path, s)
    assert p.page() == "consent"
    win._tick_widgets[0].setChecked(True)
    win._tick_widgets[1].setChecked(False)
    p.press("I understand, drive my table")
    assert W.guided(s) is False and sim.jobs[0].guided is False


def test_must2_after_the_consent_the_choice_is_the_persons(qtbot, monkeypatch, tmp_path):
    """Consent 4 given, the guidance switched off later (Preferences, the done page): the next
    START keeps it off and shows no consent page."""
    s = _settings_file(tmp_path, "[General]\ni1io_table_consent_given=4\n"
                                 "i1io_table_ask_after_each_step=false\n")
    win, sim, p = _start(qtbot, monkeypatch, tmp_path, s)
    p.idle()
    assert "consent" not in win.pages_shown
    assert W.guided(s) is False and sim.jobs[0].guided is False


def test_must2_the_consent_text_is_the_catalogues():
    body = M.M_I1IO_DRIVE_CONSENT_GUIDANCE.body
    assert SENTENCE in body and "switched on at first" not in body
