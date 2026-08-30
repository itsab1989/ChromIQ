"""ChromIQ's log must not list the Bluetooth devices around the user.

`bleak`'s DEBUG output names every device in range by its advertised name — a
phone, a television by model, the neighbours'. Measured on the author's machine:
16 devices in the clear across 7,597 lines.

That matters because the log is the thing we ask people to send when Bluetooth
fails, and because `workflow/cr30/bluetooth_report.py` redacts exactly this,
with a comment saying its file "is written to be sent to a stranger". A log full
of names meant the standard we enforce in one place was broken in the other.

Basti ruled it, 2026-08-30: stop logging them.
"""
import logging


def test_bleak_is_quietened():
    from core import logger as lg
    assert "bleak" in lg._NOISY_LIBRARIES


def test_its_running_commentary_is_dropped_but_failures_are_kept():
    """WARNING, not silence. Everything bleak says about a connection going
    wrong survives; only the neighbourhood scan is dropped."""
    from core import logger as lg
    lg._quiet_third_party()
    bl = logging.getLogger("bleak")
    assert not bl.isEnabledFor(logging.DEBUG), "device names still reach the log"
    assert not bl.isEnabledFor(logging.INFO)
    assert bl.isEnabledFor(logging.WARNING), "failures must still be recorded"


def test_chromiqs_own_bluetooth_lines_are_untouched():
    """The diagnosis reads OUR lines — quietening bleak must not quieten them."""
    from core import logger as lg
    lg._quiet_third_party()
    ours = logging.getLogger("workflow.cr30.measure_bridge")
    assert ours.isEnabledFor(logging.WARNING)
    assert not any(n.startswith("workflow") for n in lg._NOISY_LIBRARIES)
