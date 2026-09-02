"""One claim on the measuring instrument, for the reader ChromIQ drives itself.

**Why this exists.** Every "is something measuring?" guard in the app asks
:attr:`core.argyll_runner.ArgyllRunner.is_running`, and that answers purely from
PROCESS state — a ``QProcess`` or a ``Popen``. The Measure tab's CR30 session is
visible to those guards only by accident: ``chromiq-chartread -xx`` is a real
process even though it opens no instrument.

A window that drives :class:`workflow.cr30.measure_bridge.DeviceReader` directly
spawns nothing, so it is invisible to all of them. Two windows would then reach
for one instrument, and over Bluetooth a CR30 accepts a single connection and
stops advertising once it is taken. **The failure is not an error message. It is
plausible wrong colours**, because a CR30 holds its last reading indefinitely
and hands it back to whoever asks.

So the claim is explicit, process-wide, and taken by whoever opens the device.

**The holder is held by weak reference, and that is deliberate.** A claim leaked
by a window that has since been destroyed would refuse every later measurement
for the lifetime of the app — a worse fault than the one this prevents, and one
the user could not clear without restarting. When the owner object is collected,
the claim goes with it.

Only ChromIQ's own reader takes a claim. The ArgyllCMS path is left exactly as
it was: two ``spotread``/``chartread`` sessions already exclude each other
through ``ArgyllRunner.is_running``, and a ColorMunki chart read alongside a
CR30 spot read is two different instruments doing two different jobs, which is
allowed and should be.
"""
from __future__ import annotations

import threading
import weakref

from core.logger import get_logger

log = get_logger(__name__)

#: The two windows that can hold the instrument, named once. These strings are
#: IDENTIFIERS — they are compared, stored and logged — and `where_label`
#: turns one into the sentence a user reads. Keeping the two apart is not
#: ceremony: `tr(some_variable)` extracts to nothing, so a label passed
#: straight into a message would be untranslatable in all twelve languages
#: while looking perfectly translated in the source.
MEASURE_TAB = "the Measure tab"
SPOT_TOOL = "Tools ▸ Read single patches"


def where_label(label: str) -> str:
    """The holder's name, in the reader's language."""
    from core.i18n import tr
    if label == MEASURE_TAB:
        return tr("the Measure tab")
    if label == SPOT_TOOL:
        return tr("Tools ▸ Read single patches")
    return label


_lock = threading.RLock()
#: (weakref to the owner, human-readable label of where it is being used).
_claim: "tuple[weakref.ref, str] | None" = None


def _live() -> "tuple[object, str] | None":
    """The current owner and label, dropping a claim whose owner has gone."""
    global _claim
    with _lock:
        if _claim is None:
            return None
        ref, label = _claim
        owner = ref()
        if owner is None:
            # Its window is gone; the instrument is free again.
            _claim = None
            return None
        return owner, label


def holder() -> "str | None":
    """Where the instrument is being used, or None when it is free."""
    live = _live()
    return live[1] if live is not None else None


def acquire(owner: object, label: str) -> bool:
    """Claim the instrument for *owner*. True when it is yours.

    Re-claiming with the same owner succeeds — a host may open its reader more
    than once in a session (the Measure tab calibrates first and then measures
    through the same handle), and that must not deadlock against itself.
    """
    global _claim
    with _lock:
        live = _live()
        if live is not None and live[0] is not owner:
            log.info("instrument claim refused: already held by %s", live[1])
            return False
        _claim = (weakref.ref(owner), label)
        log.info("instrument claimed by %s", label)
        return True


def release(owner: object) -> None:
    """Give the instrument back. Releasing something you do not hold is a no-op,
    never an error — teardown paths run more than once and must not raise."""
    global _claim
    with _lock:
        live = _live()
        if live is None or live[0] is not owner:
            return
        log.info("instrument released by %s", live[1])
        _claim = None


def held_by_other(mine: "object | None") -> "str | None":
    """The holder's label when somebody OTHER than *mine* has the instrument.

    *mine* is the caller's own reader, or None when it has not opened one yet.
    Asked of the OBJECT, never of the label, and the difference is not
    theoretical: a second Tools ▸ Read single patches window would carry the
    same label as the first, and a label comparison would wave it straight
    through to the instrument the first one is holding.

    A window that already has the instrument is never told it is busy — that is
    what *mine* buys — so the Measure tab's calibration can open, close and
    reopen its reader within one Start without the tab refusing itself.
    """
    live = _live()
    if live is None or live[0] is mine:
        return None
    return live[1]


def holder_object() -> "object | None":
    """The object currently holding the claim, if any. For teardown: a claim
    left standing by one test would refuse the next one's session, and the
    failure would land on an innocent file."""
    live = _live()
    return live[0] if live is not None else None


def held_by(owner: object) -> bool:
    """Is *owner* the current holder?"""
    live = _live()
    return live is not None and live[0] is owner
