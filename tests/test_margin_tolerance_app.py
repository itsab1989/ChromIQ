"""The margin tolerance (Preferences > Beta, 2026-11-16) in the app:

* OFF (the default): the helper's command line is 4.3.41's, with or without
  the ruler check;
* ON: --margin-tolerance only together with --ruler, and only for a helper
  whose caps name "margin_tolerance"; with the ruler check off nothing is
  passed;
* the Measure log: one line at Start while it is on (or that an i1Pro 3 does
  not use it), one calm line for every kept strip, none for a strip it did
  not keep;
* the ruler diagnostics file (revision 3) keeps the record's "margin" and
  "trigger_wait_ms", and notes "margin_tolerance" and "i1pro2_lights_beta";
* the Preferences row: off, its (i) is the same TooltipButton as its
  neighbours', the help says what it must, the confirmation's Cancel leaves
  it off.
"""
from __future__ import annotations

import json

import pytest

from tests.test_ruler_session import _args, _session, _strip_read
from tests.test_ruler_session import _rec as _rec0


def _rec(strip, steps, result="read", **extra):
    r = _rec0(strip, steps, result=result)
    r.update(extra)
    return r
from workflow.ruler_session import RulerSession


def test_the_setting_is_off_by_default():
    from core.settings import DEFAULTS
    assert DEFAULTS["margin_tolerance_beta"] is False


def _margs(qapp, tmp_path, monkeypatch, *, ruler, margin, caps):
    from workflow.measure_manager import MeasureParams
    orig = MeasureParams.__init__

    def init(self, *a, **k):
        orig(self, *a, **k)
        self.engine_margin_tolerance = margin
    monkeypatch.setattr(MeasureParams, "__init__", init)
    return _args(qapp, tmp_path, monkeypatch, ruler=ruler, caps=caps)


CAPS = {"ruler_check", "margin_tolerance"}


@pytest.mark.parametrize("ruler", [False, True])
def test_off_adds_nothing(qapp, tmp_path, monkeypatch, ruler):
    off = _margs(qapp, tmp_path, monkeypatch, ruler=ruler, margin=False, caps=CAPS)
    assert "--margin-tolerance" not in off
    base = _args(qapp, tmp_path, monkeypatch, ruler=ruler, caps=CAPS)
    assert off == base


def test_on_needs_the_ruler_check_and_a_helper_that_knows_it(qapp, tmp_path,
                                                            monkeypatch):
    on = _margs(qapp, tmp_path, monkeypatch, ruler=True, margin=True, caps=CAPS)
    assert on.count("--margin-tolerance") == 1 and "--ruler" in on
    assert on.index("--margin-tolerance") == on.index("--ruler") + 1
    no_ruler = _margs(qapp, tmp_path, monkeypatch, ruler=False, margin=True, caps=CAPS)
    assert "--margin-tolerance" not in no_ruler and "--ruler" not in no_ruler
    old = _margs(qapp, tmp_path, monkeypatch, ruler=True, margin=True,
                 caps={"ruler_check"})
    assert "--margin-tolerance" not in old and "--ruler" in old


def test_the_tab_passes_the_setting(qapp):
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure)
    assert ('p.engine_margin_tolerance = bool(\n            self._settings.get('
            '"margin_tolerance_beta", False))') in src


def test_start_lines(tmp_path):
    ti1 = tmp_path / "runs" / "run1" / "chart.ti1"
    ti1.parent.mkdir(parents=True)
    on = RulerSession(ti1_path=ti1, lights=True).on_session(
        {"event": "ruler", "active": True, "instrument": "i1pro2",
         "firmware": 634, "margin_tolerance": "on"})
    assert sum("Margin tolerance (beta): on for this i1Pro 2" in ln for ln in on) == 1
    ti2 = tmp_path / "b" / "runs" / "run1" / "chart.ti1"
    ti2.parent.mkdir(parents=True)
    p3 = RulerSession(ti1_path=ti2).on_session(
        {"event": "ruler", "active": True, "instrument": "i1pro3",
         "firmware": 105, "margin_tolerance": "not_i1pro2"})
    assert sum("works with the X-Rite i1Pro 2 only" in ln for ln in p3) == 1
    _, plain = _session(tmp_path / "c")
    assert not any("Margin tolerance" in ln for ln in plain)


KEPT = {"tried": True, "accepted": True, "rule": "M", "left_start": 1,
        "left_end": 0, "standing": 0, "leader": True, "fit": 3.2,
        "rival": 41.0, "segments": 21, "refused_because": "Too many patches",
        "rules": "M+L 3 (2026-11-16)"}


@pytest.mark.parametrize("m,words", [
    (KEPT, "at the start of the swipe"),
    (dict(KEPT, left_start=0, left_end=1), "at the end of the swipe"),
    (dict(KEPT, left_end=1), "at both ends of the swipe"),
    (dict(KEPT, rule="L", left_start=0, leader=False,
          refused_because="Not enough patches"), "began right on the first patch"),
])
def test_one_calm_line_for_a_kept_strip(tmp_path, m, words):
    rs, _ = _session(tmp_path)
    rec = _rec("C", 300, margin=m, trigger_wait_ms=2100)
    lines = rs.on_strip(rec)
    kept = [ln for ln in lines if "margin tolerance (beta)" in ln]
    assert len(kept) == 1 and lines[0] == kept[0]
    assert kept[0].startswith("Strip C, margin tolerance (beta): ArgyllCMS "
                              "refused this reading (“" + m["refused_because"])
    assert words in kept[0] and "—" not in kept[0]
    # review 2026-11-16, MAJOR-1: the rule compares the row as a whole (a
    # mean), so the line may not claim that every patch matches
    assert "the strip as a whole matches" in kept[0]
    assert "every patch" not in kept[0]
    # and ArgyllCMS's reason is a sentence of its own, not ChromIQ's "because"
    assert "”). The " in kept[0]


def test_a_strip_not_kept_gets_no_line_and_is_filed_as_refused(tmp_path):
    rs, _ = _session(tmp_path)
    rec = _rec("C", 300, result="misread", reason="Too many patches",
               margin={"tried": True, "accepted": False, "why": "count 17",
                       "segments": 19, "rules": "M+L 3 (2026-11-16)"},
               trigger_wait_ms=0)
    lines = rs.on_strip(rec)
    assert not any("margin tolerance" in ln for ln in lines)
    doc = json.loads(rs.diag.path.read_text(encoding="utf-8"))
    e = doc["strips"][-1]
    assert e["verdict"] == "refused"
    assert e["record"]["margin"]["accepted"] is False
    assert e["record"]["trigger_wait_ms"] == 0


def test_the_diagnostics_file_keeps_the_new_fields(tmp_path):
    ti1 = tmp_path / "runs" / "run1" / "chart.ti1"
    ti1.parent.mkdir(parents=True)
    rs = RulerSession(ti1_path=ti1, lights=True)
    rs.on_session({"event": "ruler", "active": True, "instrument": "i1pro2",
                   "firmware": 634, "margin_tolerance": "on"})
    rs.on_strip(_rec("C", 300, margin=KEPT, trigger_wait_ms=2104))
    rs.on_strip_read(_strip_read("C"), other_question=False)
    rs.flush()
    doc = json.loads(rs.diag.path.read_text(encoding="utf-8"))
    assert doc["revision"] >= 3     # 4 since 4.3.47 (the pairing rule), additive
    assert doc["margin_tolerance"] == "on" and doc["i1pro2_lights_beta"] is True
    rec = doc["strips"][-1]["record"]
    assert rec["margin"] == KEPT and rec["trigger_wait_ms"] == 2104


def test_the_preferences_row_its_help_and_its_confirmation(qapp, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    from core.settings import AppSettings
    from ui.dialogs import settings_dialog as sd
    dlg = sd.SettingsDialog(AppSettings())
    try:
        box = dlg._margin_tolerance_check
        assert not box.isChecked() and "(beta)" in box.text()
        assert type(dlg._margin_tolerance_tip) is type(dlg._ruler_check_tip)
        assert dlg._margin_tolerance_tip.objectName() == \
            dlg._ruler_check_tip.objectName()
        help_text = sd.margin_tolerance_help()
        for must in ("never changes", "It needs the ruler check", "does nothing",
                     "not yet been used with a real instrument",
                     "tested only on the computer", "sessions of one tester",
                     "it kept 10", "stood in for the expected colours",
                     "moved forwards only", "taken together as a whole strip",
                     "the ruler diagnostics file notes a few more details",
                     "**Default:** off",
                     "Not enough patches", "Too many patches",
                     "Swipe didn't start and end on the media"):
            assert must in help_text, must
        # review 2026-11-16, MAJOR-2: no claim the tests cannot carry
        assert "100,000" not in help_text and "never kept a wrong" not in help_text
        assert "—" not in help_text + sd.margin_tolerance_confirmation()
        monkeypatch.setattr(QMessageBox, "exec",
                            lambda self: QMessageBox.StandardButton.Cancel)
        box.click()
        assert not box.isChecked()
        monkeypatch.setattr(QMessageBox, "exec",
                            lambda self: QMessageBox.StandardButton.Ok)
        box.click()
        assert box.isChecked()
    finally:
        dlg.reject()
        dlg.deleteLater()


def test_the_refusal_is_quoted_in_the_language_of_the_app(tmp_path, monkeypatch):
    """Re-check NIT-R2: the German line says „Zu viele Messfelder“, as the
    German (i) help and the misread window do."""
    from pathlib import Path
    rs, _ = _session(tmp_path)
    i18n_dir = Path(__file__).parents[1] / "data" / "i18n"
    de = json.loads((i18n_dir / "de.json").read_text(encoding="utf-8"))
    monkeypatch.setattr("workflow.ruler_session.tr", lambda t: de.get(t, t))
    line = rs._margin_line("A", KEPT)
    assert "„Zu viele Messfelder“" in line, line
    for lang in ("de", "es", "fr", "it", "ja", "nl", "no", "pl", "pt", "ru",
                 "sv", "uk", "zh_CN"):
        cat = json.loads((i18n_dir / f"{lang}.json").read_text(encoding="utf-8"))
        for reason in ("Too many patches", "Not enough patches",
                       "Swipe didn't start and end on the media"):
            assert cat.get(reason), (lang, reason)
