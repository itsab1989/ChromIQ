"""The settings store one test file leaves is put back before the next one runs.

The 4.3.64 gates: log_visible_lines=12 left by one file (a 12-line log in another), and Manual's
saved instrument i1 left by one file (a Barbieri film frame restored as A2 in another). The guard
is tests/helpers/settings_store_guard.py; tests/conftest.py drives it.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QSettings

from tests.helpers.settings_store_guard import SettingsStoreGuard, summary_lines

ROOT = Path(__file__).resolve().parents[1]


def _qs(ini):
    return QSettings(str(ini), QSettings.Format.IniFormat)


def test_added_changed_and_removed_values_are_put_back_and_named(tmp_path):
    ini = tmp_path / "s.ini"
    _qs(ini).setValue("custom_output_path", "/box")
    _qs(ini).setValue("kept", "x")
    g = SettingsStoreGuard(str(ini))
    g.file_begins("a.py")
    s = _qs(ini)
    s.setValue("manual_printtarg_-i_l", "i1")        # added, not synced: still seen
    s.setValue("custom_output_path", "/tmp/swept")   # changed
    s.remove("kept")                                 # removed
    s.setValue("settings_schema", 36)                # the app's own, never a leak
    assert g.file_ends() == ["custom_output_path", "kept", "manual_printtarg_-i_l"]
    after = _qs(ini)
    assert after.value("custom_output_path") == "/box" and after.value("kept") == "x"
    assert not after.contains("manual_printtarg_-i_l")
    assert int(after.value("settings_schema")) == 36
    g.file_begins("b.py")
    assert g.file_ends() == []
    assert list(g.left) == ["a.py"]


def test_a_file_whose_end_was_not_seen_is_closed_by_the_next(tmp_path):
    ini = tmp_path / "s.ini"
    g = SettingsStoreGuard(str(ini))
    g.file_begins("a.py")
    _qs(ini).setValue("k", 1)
    g.file_begins("a.py")                            # the same file goes on
    assert _qs(ini).contains("k")
    g.file_begins("b.py")
    assert g.left == {"a.py": ["k"]} and not _qs(ini).contains("k")


def test_the_summary_names_every_file(tmp_path):
    text = "\n".join(summary_lines({"tests/b.py": list("abcdefg"), "tests/a.py": ["k"]}, [0.5]))
    assert "2 test files" in text and "tests/a.py: k" in text
    assert "tests/b.py: a, b, c, d, e and 2 more" in text and "0.50 s" in text
    assert summary_lines({}, []) == []


def test_through_the_real_conftest_on_one_worker(tmp_path):
    """Two files on one xdist worker, through the suite's own hooks: the second starts clean and
    the summary names the first; the run stays green (report only)."""
    # beside the suite, never inside tests/ (other tests list that folder while a gate runs)
    first = tmp_path / "test_leaves_one.py"
    second = tmp_path / "test_starts_clean.py"
    first.write_text("def test_leaves():\n"
                     "    from core.settings import AppSettings\n"
                     "    AppSettings().set('log_visible_lines', 12)\n", encoding="utf-8")
    second.write_text("def test_starts_clean():\n"
                      "    from core.settings import AppSettings\n"
                      "    assert AppSettings().get('log_visible_lines') == 9\n",
                      encoding="utf-8")
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("PYTEST_", "CHROMIQ_"))}
    env["QT_QPA_PLATFORM"] = "offscreen"
    r = subprocess.run([sys.executable, "-m", "pytest", "-c", str(ROOT / "pytest.ini"),
                        "--rootdir", str(ROOT), "-p", "tests.conftest", "-n", "1", "-q",
                        str(first), str(second)], cwd=ROOT, env=env, timeout=600,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-1000:]
    assert "SETTINGS LEFT BEHIND" in r.stdout
    assert "test_leaves_one.py: log_visible_lines" in r.stdout
