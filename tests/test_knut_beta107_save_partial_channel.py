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


# ---- the step that was missed ---------------------------------------------
def test_on_a_stock_session_the_d_still_reaches_stdin():
    """The path that always worked must keep working."""
    m = _manager(engine=False)
    m._handle_line(_menu_line(), lambda _l: None)

    assert m._runner.stdin == ["d"]
    assert m._save_partial_state == "wait_sure"


def test_on_an_engine_session_the_d_goes_out_as_a_command():
    """Knut's case. A raw keystroke on the engine's stdin is ignored, which is
    why his instrument sat waiting until he pressed 'd' himself."""
    m = _manager(engine=True)
    m._handle_line(_menu_line(), lambda _l: None)

    assert m._runner.stdin == [], "a raw keystroke went to the engine again"
    assert m.sent_commands == [{"cmd": "done"}]
    assert m._save_partial_state == "wait_sure"


def test_a_queued_post_retry_key_takes_the_same_route():
    """The neighbouring branch had the identical fault, so it is fixed with it —
    otherwise the same silence would appear in strip navigation after a misread.
    """
    m = _manager(engine=True)
    m._save_partial_state = None
    m._pending_post_retry_key = "f"
    m._handle_line(_menu_line(), lambda _l: None)

    assert m._runner.stdin == []
    assert m.sent_commands == [{"cmd": "forward"}]
    assert m._pending_post_retry_key is None


def test_neither_branch_writes_raw_stdin_any_more():
    """Pins the rule in the source: this handler runs for engine output too, so
    every key it sends must go through the channel-aware sender."""
    src = inspect.getsource(MeasureManager._handle_line)
    # Code only: the explanation above the fix names write_stdin on purpose.
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "write_stdin" not in code, \
        "a raw keystroke is being written from the printed-line handler again"
    assert code.count("self.send_key(") >= 3, \
        "the 'd', the queued key AND the confirming 'y' must all be routed"


def test_the_confirming_yes_is_routed_too(qapp_not_needed=None):
    """His log shows the auto-'y' working today, but it was written raw on the
    same handler — the same latent gap as the 'd'. 'yes' is a mapped command, so
    routing it serves both readers."""
    m = _manager(engine=True)
    m._save_partial_state = "wait_sure"
    m._handle_line("Done ? - At least one unread patch (147, B1), "
                   "Are you sure [y/n]: ", lambda _l: None)
    assert m._runner.stdin == []
    assert {"cmd": "yes"} in m.sent_commands
    assert m._save_partial_state is None


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


def test_the_overlay_tells_the_two_cases_apart():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_overlay_toggled)
    assert "_measurement_is_empty()" in src
    # Phrases that are not split across a line continuation in the source.
    assert "There is nothing measured yet to show" in src   # the empty case
    assert "different chart" in src                          # the foreign case
    assert src.index("There is nothing measured yet to show") < src.index(
        "looks like it was made for a different chart")


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
