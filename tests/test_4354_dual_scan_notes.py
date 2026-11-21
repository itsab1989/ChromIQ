"""4.3.54: the Measure tab says before START whether the dual scan will run, and why not.

The owner (2026-11-20): a tester could not tell that the dual scan was not running; and "for
the message shown before the first strip the user shall be able to choose to never show this
again or something. because once you know this the message every time gets annoying".

Pinned here: every reason has its note in the tab's own status line; "Don't show this again"
switches off that KIND only, for good (it survives a restart), a note of another kind still
shows, Restore Factory Defaults brings them back, and the app log names the decision at every
START whether the note is shown or not. The note that M1 / M2 stopped during a measurement
(M-DUAL-ENDED) is an event of the running measurement and is not touched.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_messages as M          # noqa: E402
from workflow.dual_scan import session as D             # noqa: E402
from workflow.dual_scan import storage                  # noqa: E402

CAPS = frozenset({storage.CAPABILITY, storage.DEVICE_CAPABILITY, "i1pro3_conditions"})


def _tab(tmp_path, mode=D.MODE_M1_M2, **settings):
    from tests.test_b202_the_i1pro_generation_is_read_right import _tab as make
    tab = make(tmp_path)
    s = tab._settings
    s.set("chartread_engine", "chromiq")
    s.set("i1pro3_conditions_beta", True)
    s.set(D.SETTING, True)
    s.set(D.MODE_SETTING, mode)
    for k, v in settings.items():
        s.set(k, v)
    tab._dual_caps = lambda: CAPS
    tab._dual_model_for_plan = lambda: "i1Pro 2"
    tab._stack.setCurrentIndex(1)            # MANUAL: the filter row is there
    return tab


def _choose(tab, code):
    """The Manual filter row: off (None) or on with *code*."""
    for o in tab._m_chartread_opts:
        if o.key == "filter":
            o.checkbox.setChecked(code is not None)
            if code is not None:
                o.widget.setCurrentIndex(o.widget.findData(code))


def _highres(tab, on=True):
    for o in tab._m_chartread_opts:
        if o.key == "highres":
            o.checkbox.setChecked(on)


# ------------------------------------------------------------------ every kind has its note

def test_will_run(qapp, tmp_path):
    tab = _tab(tmp_path)
    _choose(tab, "5")
    kind, title, _b = tab._dual_note_now()
    assert kind == "will_run"
    assert title == M.M_DUAL_BEFORE_START.render(chosen="M1")[0]
    tab.close()


def test_m0_chosen_under_only_for_m1_or_m2(qapp, tmp_path):
    tab = _tab(tmp_path)
    for code in (None, "n"):
        _choose(tab, code)
        kind, title, body = tab._dual_note_now()
        assert kind == "m0_chosen" and title == M.M_DUAL_M0_CHOSEN.render(
            row="", start="", always="", option="", where="")[0]
        assert "Spectral filter type (-F)" in body and "always" in body
    tab.close()


def test_m0_chosen_under_always_still_runs(qapp, tmp_path):
    tab = _tab(tmp_path, mode=D.MODE_ALWAYS)
    _choose(tab, None)
    assert tab._dual_note_now()[0] == "will_run"
    tab.close()


def test_guided_under_only_for_m1_or_m2_reads_one_pass_and_says_where_m1_m2_are(
        qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._stack.setCurrentIndex(0)
    kind, title, body = tab._dual_note_now()
    assert kind == "guided_single" and title == M.M_DUAL_GUIDED_SINGLE.render(row="")[0]
    assert "MANUAL" in body and "Spectral filter type (-F)" in body
    tab._refresh_dual_note()
    assert 'href="dual-hide:guided_single"' in tab._status_bar_lbl.text()
    tab.close()


def test_guided_under_always_runs_the_dual_scan(qapp, tmp_path):
    tab = _tab(tmp_path, mode=D.MODE_ALWAYS)
    tab._stack.setCurrentIndex(0)
    assert tab._dual_note_now()[0] == "will_run"
    tab.close()


def test_a_continued_one_pass_measurement_gets_its_own_sentence(qapp, tmp_path):
    """could_he_tell.txt R2: under "always" a one-pass measurement continued with the dual
    scan on is refused, and the sentence says what is true ("You are continuing a measurement
    that was read with one pass per strip"), never "started as a dual scan"."""
    from tests.test_4354_dual_scan_mode import _main
    from workflow.dual_scan.reasons import REASONS
    tab = _tab(tmp_path, mode=D.MODE_ALWAYS)
    main = _main(tmp_path, dual=False)
    tab._measurement_to_continue = lambda: main
    _choose(tab, "5")
    kind, _t, body = tab._dual_note_now()
    assert kind == "cannot:mixed_scan_kind"
    assert REASONS["mixed_single_continued"] in body and "started as a dual scan" not in body
    tab.close()


def test_mixed_on_a_new_measurement_is_said_truly(qapp, tmp_path):
    """could_he_tell.txt R1: an older reading program says "mixed" on a NEW measurement; the
    line must not say "started as a dual scan"."""
    from workflow.dual_scan.reasons import REASONS
    tab = _tab(tmp_path)
    tab._dual_resume = False
    tab._session_live = True
    tab._on_dual_ended("mixed")
    assert REASONS["mixed_new"] in tab._dual_ended_text
    assert "started as a dual scan" not in tab._dual_ended_text
    tab.close()


def test_an_older_reading_program_with_the_one_pass_file_in_the_way_is_said(qapp, tmp_path):
    from tests.test_4354_dual_scan_mode import _main
    tab = _tab(tmp_path)
    _choose(tab, "5")
    main = Path(tab._ti1_path).with_suffix(".ti3")
    main.write_text(_main(tmp_path, dual=False).read_text(encoding="latin-1"),
                    encoding="latin-1")
    tab._read_builds_on_existing = lambda: True           # the box ticked, nothing to continue
    tab._measurement_to_continue = lambda: None
    tab._dual_caps = lambda: CAPS                         # an older program: no fresh_start
    assert tab._dual_note_now()[0] == "cannot:old_helper_file"
    # the bundled program (4.3.54, issue 217 fixed): it runs
    tab._dual_caps = lambda: CAPS | {"i1pro2_dual_fresh_start"}
    assert tab._dual_note_now()[0] == "will_run"
    tab.close()


def test_highres_is_said_before_start(qapp, tmp_path):
    tab = _tab(tmp_path)
    _choose(tab, "u")
    _highres(tab)
    kind, title, body = tab._dual_note_now()
    assert kind == "cannot:highres" and "High resolution spectral mode (-H)" in title
    assert "Or choose M0" in body              # only for M1 or M2, Manual
    # with M0 chosen the single scan reads with -H: nothing to refuse
    _choose(tab, None)
    assert tab._dual_note_now()[0] == "m0_chosen"
    tab.close()


def test_highres_under_always_does_not_offer_m0(qapp, tmp_path):
    tab = _tab(tmp_path, mode=D.MODE_ALWAYS)
    _highres(tab)
    kind, _t, body = tab._dual_note_now()
    assert kind == "cannot:highres" and "Or choose M0" not in body
    tab.close()


def test_nocal_is_said_before_start(qapp, tmp_path):
    tab = _tab(tmp_path)
    _choose(tab, "5")
    tab._m_nocal_cb.setChecked(True)
    assert tab._dual_note_now()[0] == "cannot:nocal"
    tab.close()


def test_the_polariser_is_said_before_start(qapp, tmp_path):
    tab = _tab(tmp_path)
    _choose(tab, "p")
    assert tab._dual_note_now()[0] == "cannot:filter"
    tab.close()


def test_not_an_i1pro2(qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._dual_model_for_plan = lambda: D.NOT_I1PRO2
    _choose(tab, "5")
    kind, title, _b = tab._dual_note_now()
    assert kind == "cannot:other_instrument" and "not an i1Pro 2" in title
    tab.close()


def test_the_engine_off_or_unable(qapp, tmp_path):
    tab = _tab(tmp_path)
    _choose(tab, "5")
    tab._dual_caps = lambda: frozenset()
    assert tab._dual_note_now()[0] == "cannot:helper"
    tab._settings.set("chartread_engine", "argyll")
    assert tab._dual_note_now()[0] == "cannot:engine"
    tab.close()


@pytest.mark.parametrize("rid", ["no_uv_tables", "uv_tile_dark", "not_available",
                                 "bad_uv_tables", "no_dual_calibration"])
def test_the_last_measurements_instrument_reason_is_said_and_forgotten(qapp, tmp_path, rid):
    """No UV light, no factory data, the tile reading with the UV light failed: known only
    from a measurement, so the next note says what the last one found."""
    tab = _tab(tmp_path)
    _choose(tab, "5")
    tab._on_dual_calibration({"ok": False, "why": "dual_" + rid})
    kind, _t, body = tab._dual_note_now()
    assert kind == "cannot:last_" + rid
    assert D.reason_sentence(rid) in body
    tab._on_dual_calibration({"ok": True})
    assert tab._dual_note_now()[0] == "will_run"
    tab.close()


def test_m1_m2_ended_during_a_measurement_is_remembered_for_the_next_note(qapp, tmp_path):
    tab = _tab(tmp_path)
    _choose(tab, "5")
    tab._on_dual_ended("dual_no_uv_tables")
    assert tab._dual_note_now()[0] == "cannot:last_no_uv_tables"
    tab.close()


def test_the_beta_off_says_nothing(qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._settings.set(D.SETTING, False)
    assert tab._dual_note_now() == ("", "", "")
    tab.close()


# ------------------------------------------------------------------ the status line, dismissal

def test_the_note_is_one_line_with_its_dont_show_link(qapp, tmp_path):
    tab = _tab(tmp_path)
    _choose(tab, "5")
    tab._refresh_dual_note()
    lbl = tab._status_bar_lbl
    assert not lbl.isHidden()
    assert M.M_DUAL_BEFORE_START.render(chosen="M1")[0] in lbl.text()
    assert 'href="dual-hide:will_run"' in lbl.text() and "Don't show this again" in lbl.text()
    from workflow.measurement_condition import condition_name
    assert lbl.toolTip() == M.M_DUAL_BEFORE_START.render(chosen=condition_name("M1"))[1]
    tab.close()


def test_a_pass_line_has_no_link(qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._dual_status("Strip A, pass 2 of 2 (UV light)", "detail")
    assert tab._status_bar_lbl.text() == "Strip A, pass 2 of 2 (UV light)"
    tab.close()


def test_dismissed_per_kind_survives_a_restart_and_the_reset_brings_it_back(qapp, tmp_path):
    tab = _tab(tmp_path)
    _choose(tab, "5")
    tab._refresh_dual_note()
    lbl = tab._status_bar_lbl
    lbl.linkActivated.emit("dual-hide:will_run")
    assert lbl.isHidden(), "dismissed: the line goes, nothing left in its place"
    assert tab._dual_before_start_text() == ("", "")
    # a different kind still shows
    _choose(tab, None)
    tab._refresh_dual_note()
    assert not lbl.isHidden() and "M0 is chosen" in lbl.text()
    # a new reason shows although another "cannot" was dismissed
    lbl.linkActivated.emit("dual-hide:m0_chosen")
    _choose(tab, "u")
    _highres(tab)
    tab._refresh_dual_note()
    assert "High resolution" in lbl.text()
    lbl.linkActivated.emit("dual-hide:cannot:highres")
    tab._m_nocal_cb.setChecked(True)
    _highres(tab, False)
    tab._refresh_dual_note()
    assert not lbl.isHidden() and "Skip initial calibration" in lbl.text()
    # a restart: the same file, a new store and a new tab
    from core.settings import AppSettings
    from PyQt6.QtCore import QSettings
    s2 = AppSettings()
    s2._qs = QSettings(tab._settings._qs.fileName(), QSettings.Format.IniFormat)
    hidden = set(str(s2.get("dual_scan_notes_hidden")).split(","))
    assert hidden == {"will_run", "m0_chosen", "cannot:highres"}
    # Restore Factory Defaults
    tab._settings.reset_to_defaults()
    assert tab._dual_notes_hidden() == set()
    tab.close()


def test_the_app_log_says_the_decision_also_when_the_note_is_off(qapp, tmp_path, caplog):
    tab = _tab(tmp_path)
    _choose(tab, None)
    tab._dual_hide_note("m0_chosen")
    with caplog.at_level(logging.INFO):
        tab._log_dual_decision("hand")
    lines = [r.getMessage() for r in caplog.records if "dual scan decision" in r.getMessage()]
    assert len(lines) == 1, lines
    assert "kind=m0_chosen" in lines[0] and "mode=m1_m2" in lines[0]
    assert "hidden=on" in lines[0] and "M0 is chosen" in lines[0]
    tab.close()


def test_the_session_header_names_the_mode():
    from core import beta_registry as br
    assert D.MODE_SETTING in br.LOGGED_KEYS


def test_the_stopped_line_is_not_a_dismissible_note(qapp, tmp_path):
    """M-DUAL-ENDED is an event of the running measurement: never a note with a link."""
    tab = _tab(tmp_path)
    tab._dual_hide_note("will_run")
    tab._session_live = True                 # a session runs: no note before START
    tab._dual_status("")
    tab._on_dual_ended("dual_dual_needs_ruler")
    lbl = tab._status_bar_lbl
    assert lbl.isHidden() or "dual-hide" not in lbl.text()
    assert getattr(tab, "_dual_status_kind", "") == ""
    assert tab._dual_ended_text
    tab.close()
