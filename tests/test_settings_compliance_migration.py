"""schema-23 migration (#182): the Measurement Report's two thresholds become
per-row limits in named limit sets. A pair that echoes the factory 2.0 / 3.0 is
dropped; a moved value lives on as an override on the ChromIQ default set, per
value; the two old keys are removed so Settings → Save cannot resurrect them."""
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings   # noqa: E402

from core.settings import (AppSettings, parse_compliance_overrides,   # noqa: E402
                           serialize_compliance_overrides)


def _settings(tmp_path: Path, avg=None, mx=None, schema=22) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s._qs.setValue("settings_schema", schema)
    if avg is not None:
        s._qs.setValue("report_pass_threshold_avg", avg)
    if mx is not None:
        s._qs.setValue("report_pass_threshold_max", mx)
    return s


def test_the_factory_pair_is_dropped_and_no_override_is_written(tmp_path):
    s = _settings(tmp_path, 2.0, 3.0)
    dropped = s.migrate()
    assert any("report_pass_threshold" in d for d in dropped)
    assert s._qs.value("report_pass_threshold_avg", None) is None
    assert s._qs.value("report_pass_threshold_max", None) is None
    assert s.get_compliance_overrides() == {}


def test_a_moved_average_lands_on_the_three_average_rows_only(tmp_path):
    s = _settings(tmp_path, "2.5", 3.0)          # INI persists numbers as strings
    s.migrate()
    ov = s.get_compliance_overrides()
    assert ov == {"chromiq_default": {"all_de00_avg": 2.5, "best95_de00_avg": 2.5,
                                      "worst5_de00_avg": 2.5}}


def test_a_moved_maximum_lands_on_the_two_maximum_rows_only(tmp_path):
    s = _settings(tmp_path, 2.0, 4.0)
    s.migrate()
    assert s.get_compliance_overrides() == {
        "chromiq_default": {"all_de00_max": 4.0, "all_de00_p95": 4.0}}


def test_only_one_old_key_stored_is_handled(tmp_path):
    s = _settings(tmp_path, avg=1.5)
    s.migrate()
    assert s.get_compliance_overrides()["chromiq_default"]["all_de00_avg"] == 1.5
    assert "all_de00_max" not in s.get_compliance_overrides()["chromiq_default"]


def test_unset_keys_write_nothing_and_the_schema_is_stamped(tmp_path):
    s = _settings(tmp_path)
    dropped = s.migrate()
    assert not any("report_pass_threshold" in d for d in dropped)
    assert s.get_compliance_overrides() == {}
    assert int(s._qs.value("settings_schema")) == 23


def test_the_migration_runs_once(tmp_path):
    s = _settings(tmp_path, 2.5, 3.0)
    s.migrate()
    # an older ChromIQ on the same file writes the key again …
    s._qs.setValue("report_pass_threshold_avg", 9.0)
    assert s.migrate() == []                     # … and schema 23 ignores it
    assert s.get_compliance_overrides()["chromiq_default"]["all_de00_avg"] == 2.5


def test_an_existing_override_blob_is_merged_not_replaced(tmp_path):
    s = _settings(tmp_path, 2.5, 3.0)
    s._qs.setValue("compliance_set_overrides",
                   serialize_compliance_overrides({"chromiq_tight": {"all_de00_avg": 0.8}}))
    s.migrate()
    ov = s.get_compliance_overrides()
    assert ov["chromiq_tight"] == {"all_de00_avg": 0.8}
    assert ov["chromiq_default"]["all_de00_avg"] == 2.5


def test_garbage_values_are_ignored_not_fatal(tmp_path):
    s = _settings(tmp_path, "abc", "-1")
    s.migrate()
    assert s.get_compliance_overrides() == {}
    assert s._qs.value("report_pass_threshold_avg", None) is None


def test_the_blob_helpers_are_tolerant():
    assert parse_compliance_overrides("") == {}
    assert parse_compliance_overrides("{bad") == {}
    assert parse_compliance_overrides('["a"]') == {}
    assert parse_compliance_overrides('{"chromiq_default": {"all_de00_avg": "2.5", '
                                      '"all_de00_max": null, "x": "junk"}, "y": 1}') == {
        "chromiq_default": {"all_de00_avg": 2.5, "all_de00_max": None}}
    assert serialize_compliance_overrides({}) == ""


def test_the_new_defaults_exist_and_the_old_keys_do_not():
    from core.settings import DEFAULTS
    assert "report_pass_threshold_avg" not in DEFAULTS
    assert "report_pass_threshold_max" not in DEFAULTS
    assert DEFAULTS["compliance_default_set"] == "chromiq_default"
    assert DEFAULTS["compliance_allow_edit_after_measurement"] is False
    assert DEFAULTS["compliance_set_overrides"] == ""
    assert DEFAULTS["compliance_columns_shown"] == ""
