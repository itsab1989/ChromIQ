"""#130 (Knut, 2026-07-30): "Save Partial & Quit" after a misread hung.

His decisive test: *"When reading failed, the reading failed window comes, then I
select Save Partial and Quit button. Now instrument hangs. I then tested to press
r. Nothing happened. I then tested to press d, and the session saved and exited."*

His log shows the first half of the chain working — the Return arrives, the reader
returns to the strip menu (``Ready to read strip pass B``) — and then silence. The
``d`` that makes chartread write the ``.ti3`` was never delivered.

Cause: the branch that reacts to the PRINTED strip-menu line wrote the ``d``
straight to the process's stdin. That is how you talk to stock ArgyllCMS
chartread, but ChromIQ's own reading engine takes structured JSON commands and
ignores raw keystrokes — so on an engine session the follow-up went nowhere.
``send_key`` already routes by channel, and is what every other call site uses.

I had three wrong theories about this bug before his test narrowed it to one step;
these tests pin the step itself rather than any of the reasoning around it.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measure_manager import MeasureManager    # noqa: E402


class _Runner:
    """Records what would reach the process, on either channel."""

    def __init__(self):
        self.stdin: list[str] = []
        self.is_running = True

    def write_stdin(self, text: str) -> None:
        self.stdin.append(text)


def _manager(*, engine: bool):
    m = MeasureManager.__new__(MeasureManager)      # no Qt parent needed
    m._runner = _Runner()
    m._engine_active = engine
    # The run supplies its own values (chartread -x); see save_partial_and_quit().
    m._external_values = False
    m._user_quit = False
    m._save_partial_state = "wait_strip_menu"
    m._pending_post_retry_key = None
    m._guided_state = "disabled"
    m._at_retry_prompt = True
    m.sent_commands = []
    m.send_command = lambda cmd: m.sent_commands.append(cmd)   # type: ignore
    m.stripe_changed = type("S", (), {"emit": staticmethod(lambda *_a: None)})()
    return m


def _menu_line() -> str:
    """The line chartread prints when the strip menu comes back — the exact
    wording from Knut's log."""
    return "Ready to read strip pass B"


# ---- what survives of that fix -------------------------------------------
# The 'd' and 'y' steps this file was written for are GONE: Save-Partial is two
# 'q' commands now (Knut established the protocol by hand — see
# test_knut_beta109_two_q_save_partial.py), so the strip-menu chain they belonged
# to is unreachable and has been removed rather than left to look alive.
#
# The channel lesson still stands for the branch that remains, and that is what
# is tested here: this handler sees the engine's printed output too, so anything
# it sends must go out as a command rather than a raw keystroke.

def test_a_queued_post_retry_key_goes_out_as_a_command(qapp=None):
    m = _manager(engine=True)
    m._save_partial_state = None
    m._pending_post_retry_key = "f"
    m._handle_line(_menu_line(), lambda _l: None)

    assert m._runner.stdin == [], "a raw keystroke went to the engine again"
    assert m.sent_commands == [{"cmd": "forward"}]
    assert m._pending_post_retry_key is None


def test_the_same_key_still_reaches_stdin_on_a_stock_session():
    m = _manager(engine=False)
    m._save_partial_state = None
    m._pending_post_retry_key = "f"
    m._handle_line(_menu_line(), lambda _l: None)
    assert m._runner.stdin == ["f"]


def test_the_removed_chain_is_really_gone():
    """It only ever worked when the reader happened to be at the strip menu, and
    left the session hanging from a misread — so it must not survive as code that
    looks live."""
    src = inspect.getsource(MeasureManager)
    assert "wait_strip_menu" not in src
    assert "wait_sure" not in src


def test_the_handler_sends_nothing_raw():
    src = inspect.getsource(MeasureManager._handle_line)
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "write_stdin" not in code


def test_send_key_is_what_routes_by_channel():
    """The reason the fix is a one-word change: send_key already knows both
    channels, and is what every other call site uses."""
    src = inspect.getsource(MeasureManager.send_key)
    assert "if self._engine_active:" in src
    assert "command_for_key" in src
    assert "self._runner.write_stdin(key)" in src


def test_the_engine_knows_the_done_command():
    """If 'd' ever stopped mapping, the fix above would go quiet in exactly the
    way the bug did — so the mapping is asserted, not assumed."""
    from workflow.chartread_engine import command_for_key
    assert command_for_key("d") == {"cmd": "done"}
    assert command_for_key("f") == {"cmd": "forward"}


# ---- item 2: an empty backup is not readings (Knut, #130 2026-07-30) -------
def _ti3(path, rows: int) -> None:
    body = "\n".join(f"{i} A{i} 50 50 50 20 20 20" for i in range(1, rows + 1))
    path.write_text(
        "CTI3\n\n"
        'DESCRIPTOR "measurement"\n'
        'TARGET_INSTRUMENT "X-Rite ColorMunki"\n\n'
        "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {rows}\nBEGIN_DATA\n"
        + (body + "\n" if body else "")
        + "END_DATA\n", encoding="utf-8")


def test_an_empty_measurement_is_recognised_as_empty(tmp_path):
    """*"There were no measurements at all… it should have been detected that the
    measurements were empty."*"""
    from ui.tabs.tab_measure import _cgats_has_no_readings
    empty = tmp_path / "empty.ti3"
    _ti3(empty, 0)
    assert _cgats_has_no_readings(empty) is True

    header_only = tmp_path / "header.ti3"
    header_only.write_text("CTI3\nNUMBER_OF_SETS 12\n", encoding="utf-8")
    assert _cgats_has_no_readings(header_only) is True, \
        "a file with no data section at all holds no readings either"


def test_a_real_measurement_is_not_called_empty(tmp_path):
    from ui.tabs.tab_measure import _cgats_has_no_readings
    real = tmp_path / "real.ti3"
    _ti3(real, 12)
    assert _cgats_has_no_readings(real) is False


def test_an_unreadable_file_is_not_reported_as_empty(tmp_path):
    """Unreadable is a different problem, and claiming "no readings" would send
    the user to measure again when the readings may be perfectly fine."""
    from ui.tabs.tab_measure import _cgats_has_no_readings
    missing = tmp_path / "not-there.ti3"
    assert _cgats_has_no_readings(missing) is False


def test_the_recovery_refuses_an_empty_backup():
    """It must not turn an empty backup into "this run has a measurement" — that
    is what made the overlay blame a chart mismatch."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._recover_stranded_partial)
    assert "_cgats_has_no_readings(partial)" in src
    assert "nothing to carry on from" in src
    # and it is checked BEFORE the offer window is built
    assert src.index("_cgats_has_no_readings") < src.index("QMessageBox(self)")


def test_the_overlay_tells_the_cases_apart():
    """Knut's requirement, now covering THREE causes rather than two.

    His point in #130 was that an empty measurement must not be reported as a
    foreign one, because the two call for opposite actions. Basti found the
    third on 2026-08-08: a chart made before the layout engine records no patch
    positions, so the overlay has nowhere to draw even though the measurement is
    perfect — and that was being reported as foreign too, which invites throwing
    away a good measurement.

    The decision now lives in `_overlay_failure_reason`, so this checks the
    reasons and their windows rather than the old inline `_measurement_is_empty`
    call.
    """
    from ui.tabs.tab_measure import TabMeasure
    decide = inspect.getsource(TabMeasure._overlay_failure_reason)
    assert "_measurement_is_empty()" in decide, \
        "the empty case is no longer established from the file"
    for reason in ('"empty"', '"no_geometry"', '"mismatch"'):
        assert reason in decide, f"{reason} is not distinguished any more"

    src = inspect.getsource(TabMeasure._on_overlay_toggled)
    assert 'reason == "empty"' in src
    assert 'reason == "no_geometry"' in src
    # Each cause gets its own window, and the empty one is still handled first.
    assert "This measurement holds no readings yet" in src        # empty
    assert "record where its patches are" in src                  # no geometry
    assert "made for a different chart" in src                    # foreign
    assert src.index("This measurement holds no readings yet") < src.index(
        "record where its patches are")


def test_both_checks_share_one_definition_of_empty():
    """Two places ask the same question; one answer, so they cannot disagree."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._measurement_is_empty)
    assert "_cgats_has_no_readings(ti3)" in src


# ---- item 4: say where the measurement went (Knut approved option 1) -------
def test_the_restore_notice_names_the_old_folder():
    """*"Yes, proceeding with (1)."* — the chart comes back, and ChromIQ says the
    measurement is in old/<date>/ rather than leaving the Measure tab silently
    without its resume and overlay boxes."""
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._note_archived_measurement_after_restore)
    assert "old/{folder}" in src
    assert "Refine / resume" in src, "it must explain WHY the boxes are absent"
    assert "readings are safe" in src


def test_nothing_is_moved_back_by_the_notice():
    """Option 1, not 3: readings the user displaced are never resurrected behind
    their back."""
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._note_archived_measurement_after_restore)
    for forbidden in ("shutil.copy", "shutil.move", "write_bytes", "rename"):
        assert forbidden not in src, f"the notice is moving files ({forbidden})"


def test_the_notice_is_silent_when_there_is_nothing_to_say():
    """No archived measurement, or the run still has its own — say nothing."""
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._note_archived_measurement_after_restore)
    assert "run.measurement_ti3.exists()" in src
    assert "not run.old_dir.is_dir()" in src


def test_it_runs_after_the_restore_has_refreshed_everything():
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._on_verify_chart_restored)
    assert "_note_archived_measurement_after_restore()" in src
    assert src.index("_target_bar.refresh()") < src.index(
        "_note_archived_measurement_after_restore()")


def test_the_notice_never_breaks_a_restore():
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._note_archived_measurement_after_restore)
    assert "except Exception" in src
