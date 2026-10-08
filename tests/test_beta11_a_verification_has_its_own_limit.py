"""Three patch-read limits (beta 11, Knut #182 5983470377).

Answer 1: *"yes, 10, and own threshold row for this in Preferences -->
Measurements "Flag a patch when..."*: a verification judged against its
profile's prediction has its own limit, default ΔE 10, used exactly when the
expected colours are that prediction. Answer 2: the limit for a chart made
from a profile is 20, no longer ArgyllCMS's 30.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import patch_flags as pf                       # noqa: E402
from workflow import verify_expected as ve                   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


class _S(dict):
    def get(self, k, default=None):
        return super().get(k, default)


def test_the_defaults():
    assert pf.PREDICTION_DEFAULT_DE == 10.0
    assert pf.ACCURATE_DEFAULT_DE == 20.0
    assert pf.ESTIMATED_DEFAULT_DE == 95.0
    assert pf.warn_limit(_S(), False) == 95.0
    assert pf.warn_limit(_S(), True) == 20.0
    assert pf.warn_limit(_S(), False, predicted=True) == 10.0


@pytest.mark.parametrize("accurate", [False, True])
def test_the_prediction_decides_whatever_the_chart_file_says(accurate):
    s = _S(patch_read_warn_de_estimated=90.0, patch_read_warn_de_accurate=25.0,
           patch_read_warn_de_prediction=7.5)
    assert pf.warn_limit(s, accurate, predicted=True) == 7.5
    assert pf.warn_limit(s, accurate) == (25.0 if accurate else 90.0)


def test_the_tab_uses_the_verification_limit_only_for_a_prediction(qapp, tmp_path):
    import test_k182_verify_expected_prediction as t
    tab = t._tab(tmp_path, {"chartread_engine": "chromiq",
                            "patch_warn_outlier_fence": True,
                            "patch_read_warn_de_prediction": 12.0})
    tab._live_expected = ve.LiveExpected(ve.SOURCE_PREDICTION, "t", t.PRED)
    assert tab._patch_warn_limit() == 12.0
    assert tab._use_outlier_fence() is False          # strip test stays off
    tab._on_strip_measured(t._shifted_strip("A"))
    assert t._info(tab, "A1")["warn_de"] == 12.0
    # The fallbacks (no record, profile newer) take the chart's own limit.
    for fallback in (ve.estimate("no record"),
                     ve.estimate("newer", profile_newer=True), None):
        tab._live_expected = fallback
        assert tab._patch_warn_limit() == 95.0


def test_preferences_show_and_save_the_third_row(qapp, monkeypatch):
    from PyQt6.QtWidgets import QDialog, QLabel
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    monkeypatch.setattr(QDialog, "accept", lambda self: None)
    s = AppSettings()
    s.set("patch_read_warn_de_prediction", 14.0)
    d = SettingsDialog(s, None)
    try:
        assert d._patch_warn_pred_spin.value() == 14.0
        texts = {w.text() for w in d.findChildren(QLabel)}
        assert "on a verification judged against its profile:" in texts
        d._patch_warn_pred_spin.setValue(8.0)
        d._save_and_close()
        assert float(s.get("patch_read_warn_de_prediction")) == 8.0
    finally:
        d.deleteLater()


def test_the_help_names_three_limits_and_the_new_defaults():
    import inspect
    from ui.dialogs import settings_dialog
    src = inspect.getsource(settings_dialog)
    assert "TWO LIMITS" not in src and "THREE LIMITS" not in src
    assert "tr(LIMITS_PURPOSE_HELP)" in src
    # Term: "made with a pre-conditioning profile" (Knut, #182 5984174575).
    assert ("20 ΔE for a chart made \"\n            \"with a pre-conditioning "
            "profile, 10 ΔE for a verification") in src


def test_the_limits_say_what_they_are_for_in_both_places():
    """Knut, #182 5983733592: the help explains the purpose: misreads, not
    colours the printer cannot reach; one paragraph in both places."""
    import inspect
    from ui.dialogs import settings_dialog as sd
    from ui.tabs import tab_measure as tm
    assert sd.LIMITS_PURPOSE_HELP == tm.LIMITS_PURPOSE_HELP
    text = sd.LIMITS_PURPOSE_HELP
    assert "catch misreads" in text and "not a mark for colours" in text
    for d in ("default ΔE 95", "default ΔE 20", "default ΔE 10"):
        assert d in text
    assert "\u2014" not in text
    assert "tr(LIMITS_PURPOSE_HELP)" in inspect.getsource(tm)


#: k44 (beta 15): the checkbox is named after its function, the strip test
_STRIP_CHECK_LABEL = ("Strip test: flag a patch past the limit only if it "
                      "also stands out from its own strip")


def test_the_help_quotes_the_strip_check_as_its_checkbox_reads():
    """The help names the strip check by quoting its Preferences checkbox, so
    the quote must be the checkbox's own words, in every language (review of
    beta 11: it quoted "only flag a patch that ALSO stands out", which no
    checkbox says, and each catalogue its own paraphrase of that)."""
    import glob
    import inspect
    import json
    from ui.dialogs import settings_dialog as sd
    assert sd.STRIP_TEST_LABEL == _STRIP_CHECK_LABEL
    assert "tr(STRIP_TEST_LABEL)" in inspect.getsource(sd)
    assert f"“{_STRIP_CHECK_LABEL}”" in sd.LIMITS_PURPOSE_HELP
    root = os.path.join(os.path.dirname(__file__), "..", "data", "i18n")
    files = sorted(glob.glob(os.path.join(root, "*.json")))
    assert len(files) >= 13
    for f in files:
        with open(f, encoding="utf-8") as fh:
            cat = json.load(fh)
        label = cat[_STRIP_CHECK_LABEL]
        assert label in cat[sd.LIMITS_PURPOSE_HELP], os.path.basename(f)
