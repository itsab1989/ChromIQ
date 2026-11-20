"""M3 (review of the app-log branch, 20 Nov 2026): the first log a tester sends
after updating held every older session unscrubbed, because ``chromiq.log`` is
appended to and rotated. At the first start of a build with the privacy filter
the log and its rotated copies pass through the filter ONCE (atomic replace,
the original kept on any failure, a marker line in the new log), and the crash
log is cleaned at every start before faulthandler opens it."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from core import log_privacy as lp

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def ident():
    lp.reset_for_tests(homes=["/Users/basti"], names=["basti"],
                       phrases=["Sebastian Muster"], hosts=["Bastis-Mac-mini"])
    yield
    lp.reset_for_tests()


OLD = ("\n=== ChromIQ session started — 2026-11-01 10:00:00  v4.3.49  (darwin, py 3.14)\n"
       "2026-11-01 10:00:01 [DEBUG] core.settings: Settings loaded from "
       "/Users/basti/Library/Preferences/com.chromiq.ChromIQ.plist\n"
       "2026-11-01 10:00:02 [INFO] workflow.cr30.device_info: CR30 connected over USB: "
       "model CR30, serial 12345678, internal id AB12CD34\n"
       "2026-11-01 10:00:03 [INFO] core.alert_sound: alert sounds play through "
       "'Sebastians AirPods'\n"
       "2026-11-01 10:00:04 [INFO] x: strip A attempt 1 kept dE 1.2\n")


def _write(p: Path, text: str, extra: bytes = b"") -> None:
    p.write_bytes(text.encode("utf-8") + extra)


def test_the_log_and_its_rotated_copies_are_cleaned_once(ident, tmp_path):
    _write(tmp_path / "chromiq.log", OLD, b"\xff\xfe broken bytes kept\n")
    _write(tmp_path / "chromiq.log.1", OLD)
    _write(tmp_path / "chromiq.log.5", OLD)
    res = lp.clean_old_logs(tmp_path)
    assert not res["failed"]
    assert {f for f, _n in res["cleaned"]} == {"chromiq.log", "chromiq.log.1", "chromiq.log.5"}
    for name in ("chromiq.log", "chromiq.log.1", "chromiq.log.5"):
        data = (tmp_path / name).read_bytes()
        text = data.decode("utf-8", "surrogateescape")
        for raw in ("/Users/basti", "12345678", "AB12CD34", "Sebastian", "Bastis"):
            assert raw not in text, (name, raw)
        assert "~/Library/Preferences" in text and "<user>s AirPods" in text
        assert "strip A attempt 1 kept dE 1.2\n" in text      # ordinary lines unchanged
        assert "v4.3.49" in text                              # the banner stays
    assert b"\xff\xfe broken bytes kept\n" in (tmp_path / "chromiq.log").read_bytes()
    assert (tmp_path / lp.CLEAN_MARKER).read_text(encoding="utf-8").strip() == str(lp.CLEAN_VERSION)
    assert not list(tmp_path.glob("*.cleaning"))
    # once: a second start does not touch the files again
    _write(tmp_path / "chromiq.log.1", OLD)
    assert lp.clean_old_logs(tmp_path) is None
    assert "/Users/basti" in (tmp_path / "chromiq.log.1").read_text(encoding="utf-8")


def test_a_failed_rewrite_keeps_the_original_and_says_so(ident, tmp_path, monkeypatch, caplog):
    _write(tmp_path / "chromiq.log", OLD)
    before = (tmp_path / "chromiq.log").read_bytes()

    def refuse(*_a, **_k):
        raise PermissionError("the file is in use")
    monkeypatch.setattr(lp.os, "replace", refuse)
    res = lp.clean_old_logs(tmp_path)
    assert res["failed"] and res["failed"][0][0] == "chromiq.log"
    assert (tmp_path / "chromiq.log").read_bytes() == before      # never lost
    assert not list(tmp_path.glob("*.cleaning"))
    assert not (tmp_path / lp.CLEAN_MARKER).exists()              # tried again next start
    import logging
    with caplog.at_level(logging.INFO):
        lp.log_cleaning_result(res)
    said = " ".join(r.getMessage() for r in caplog.records)
    assert "could not clean chromiq.log" in said and "original is kept" in said


def test_the_crash_log_is_cleaned_before_faulthandler_opens_it(ident, tmp_path):
    from core import crash_log
    crash = tmp_path / crash_log.FILE_NAME
    crash.write_text('  File "/Users/basti/develop/ChromIQ/main.py", line 3 in main\n',
                     encoding="utf-8")
    crash_log.clean_previous(tmp_path)
    assert "/Users/basti" not in crash.read_text(encoding="utf-8") and "~/develop" in crash.read_text(encoding="utf-8")
    import inspect
    src = inspect.getsource(crash_log.arm)
    assert src.index("clean_previous(") < src.index("open(")


def test_the_real_start_cleans_an_old_log_and_writes_the_marker_line(tmp_path):
    """configure_logging, as main.py's import runs it, in a fresh process."""
    home = os.path.expanduser("~")
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "chromiq.log").write_text(
        f"2026-11-01 10:00:01 [DEBUG] core.settings: Settings loaded from {home}/Library/x.plist\n"
        "2026-11-01 10:00:02 [INFO] i1pro: Serial Number:     1234567\n", encoding="utf-8")
    (logs / "chromiq.log.1").write_text(
        "2026-10-01 10:00:02 [INFO] i1pro: Serial Number:     1234567\n", encoding="utf-8")
    env = dict(os.environ, CHROMIQ_LOG_DIR=str(logs),
               CHROMIQ_SETTINGS_FILE=str(tmp_path / "settings.ini"),
               QT_QPA_PLATFORM="offscreen")
    code = ("from core.logger import configure_logging; configure_logging(); "
            "import logging; logging.getLogger('t').info('after')")
    r = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), env=env,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    assert r.returncode == 0, r.stderr
    text = (logs / "chromiq.log").read_text(encoding="utf-8")
    assert home not in text and "1234567" not in text
    assert "log privacy: the older sessions in this log were passed through" in text
    assert (logs / lp.CLEAN_MARKER).is_file()
    # one key for every file (found on screen: the settings import inside the cleaning
    # configured logging again, and the rotated copy got another code)
    import re
    one = re.findall(r"<sn:[0-9a-f]{8}>", text)
    two = re.findall(r"<sn:[0-9a-f]{8}>", (logs / "chromiq.log.1").read_text(encoding="utf-8"))
    assert one and one == two, (one, two)
    assert text.count("log privacy: the older sessions") == 1
    assert not (logs / (lp.CLEAN_MARKER + ".lock")).exists()


def test_an_old_line_that_logged_a_salt_or_a_device_setting_is_hidden(ident):
    """Found on screen (final fix round): 4.3.49 logged every setting with %r, the table's
    reach salt among them; the filter hides the value of those keys in an old line too."""
    old = ("2026-11-01 10:00:06,000 [DEBUG] core.settings: settings.set i1io_table_reach = "
           "'{\"salt\": \"b39d28f5aa11c0de\", \"tables\": {\"f0874b8c203e1383\": {\"v\": 2}}}'")
    out = lp.safe_scrub(old)
    assert "b39d28f5" not in out and "f0874b8c" not in out
    assert out.endswith("settings.set i1io_table_reach = <value not logged>")
    assert "b39d" not in lp.safe_scrub('{"salt": "b39d28f5aa11c0de"}')
    new = "settings.set i1io_table_reach = <380 characters, not logged>"
    assert lp.safe_scrub(new) == new
    assert "CM454M0223" not in lp.safe_scrub(
        "settings.set cr30_last_device_info = '{\"model\": \"CR30\", \"x\": \"CM454M0223\"}'")


def test_one_process_cleans_a_second_one_leaves_it(ident, tmp_path):
    import os
    import time
    _write(tmp_path / "chromiq.log", OLD)
    lock = tmp_path / (lp.CLEAN_MARKER + ".lock")
    lock.write_text("", encoding="utf-8")
    assert lp.clean_old_logs(tmp_path) is None                      # another one is at it
    assert "/Users/basti" in (tmp_path / "chromiq.log").read_text(encoding="utf-8")
    old = time.time() - 120
    os.utime(lock, (old, old))                                       # a crashed cleaner's
    res = lp.clean_old_logs(tmp_path)
    assert res and not res["failed"] and not lock.exists()
    assert "/Users/basti" not in (tmp_path / "chromiq.log").read_text(encoding="utf-8")
