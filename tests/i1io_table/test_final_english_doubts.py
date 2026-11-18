"""Final fix round: the translation challenger's English doubts (challenger/ENGLISH_DOUBTS.md),
each answered in the English source."""
from __future__ import annotations

import inspect

from ui import i1io_table_window as W
from workflow import measurement_messages as M


def test_313_the_way_back_is_the_power_switch_everywhere():
    for msg in (M.M_I1IO_DRIVE_LINK_LOST, M.M_I1IO_DRIVE_LINK_LOST_SWITCH_OFF,
                M.M_I1IO_DRIVE_SWITCH_OFF):
        body = msg.body
        assert "power switch" in body
        assert "or unplug the table's USB cable" not in body
    assert "Unplugging its USB cable is not enough" in M.M_I1IO_DRIVE_LINK_LOST.body


def test_405_406_the_dead_not_built_reasons_are_gone():
    src = inspect.getsource(W)
    assert "is not built yet" not in src
    assert "strip_rows_not_built" not in src


def test_the_plainer_words():
    assert W.choice_label("arm_felt", "holds") == "It does not move"
    assert "if it does not move" in M.M_I1IO_DRIVE_ARM_FELT.body
    src = inspect.getsource(W)
    assert "Arm: its position is not known." in src and "where it is is not known" not in src
    assert "Now: row {row} has been read." in src
    assert "because you pressed Stop." in src and "because you stopped it" not in src
    assert M.M_I1IO_DRIVE_USB_GONE.title == "ChromIQ lost the connection to the table"
    assert "disappeared" not in M.M_I1IO_DRIVE_USB_GONE.body
    start = M.M_I1IO_DRIVE_START_UP.body
    assert "ChromIQ's tester program has sent this start-up to a real table once" in start
    from ui.dialogs import settings_dialog as S
    assert "ChromIQ asks after every step of an i1iO table measurement whether the table did" \
        in " ".join(inspect.getsource(S).split()).replace('" "', "")
