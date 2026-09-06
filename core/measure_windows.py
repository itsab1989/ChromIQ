"""The windows a measurement can raise, and the sound each one plays.

Knut asked for this as a table the user can actually read (#131, 2026-07-27),
then for row 1 to be given in full (2026-07-28), and then — after the completion
audit — for it to be checked against what the code actually does
(*"ensure that the help text in the preferences sounds tab … is updated and
correct"*, 2026-07-28).

That check found three things, all fixed here:

* a row named a window by a name it does not have (**Instrument busy** — the
  window is called *Instrument Not Available*);
* a row called **Instrument error (other)** stood for four separate windows the
  user can actually meet, and named none of them;
* the **Averaging Failed** window was missing, because it had no sound at all —
  now it has one.

**The HTML is built from the rows.** It used to be a second copy of the same
table, written out by hand, so the two could disagree — which is exactly the
kind of fault Knut asked me to look for. There is now one source.

Sound names are the ones in Preferences → Sounds, never the internal
identifiers.
"""
from __future__ import annotations

import html

from core.i18n import tr

#: (window, reading mode, Preferences sound label)
WINDOW_ROWS = [
    (tr("Strip read failed"), tr("Strip reading"),
     tr("Slow down, or Strip read failed — ChromIQ reads Argyll's own wording and "
     "picks the one that fits (see the third table)")),
    (tr("Patch read failed"), tr("Patch by patch"), tr("Strip read failed")),
    (tr("Strip read quickly"), tr("Strip reading"), tr("Slow down")),
    (tr("Wrong strip read"), tr("Strip reading"), tr("Strip read failed")),
    (tr("Unexpected Colour Response"), tr("Both"), tr("Patch reading looks off")),
    (tr("Strip may be misaligned"), tr("Strip reading"), tr("Strip read failed")),
    (tr("Strip read interrupted"), tr("Strip reading"), tr("Strip read failed")),
    (tr("Patches still unread"), tr("Both"), tr("Strip read failed")),
    (tr("Averaging failed"), tr("Both"), tr("Strip read failed")),
    (tr("Calibration required"), tr("Both"), tr("Instrument error")),
    (tr("Confirm abort"), tr("Both"), tr("Instrument error")),
    (tr("Instrument disconnected"), tr("Both"), tr("Instrument error")),
    (tr("No instrument found"), tr("Both"), tr("Instrument error")),
    (tr("Instrument Not Available (in use by another program)"), tr("Both"),
     tr("Instrument error")),
    (tr("Instrument in Wrong Position"), tr("Both"), tr("Instrument error")),
    (tr("Instrument Not Accessible (claimed by a virtual machine)"), tr("Both"),
     tr("Instrument error")),
    (tr("Instrument Failed to Initialize"), tr("Both"), tr("Instrument error")),
    (tr("Instrument Type Mismatch"), tr("Both"), tr("Instrument error")),
    (tr("Correction File Failed to Load"), tr("Both"), tr("Instrument error")),
    (tr("Instrument Mode Rejected"), tr("Both"), tr("Instrument error")),
    (tr("Instrument Error (anything else the instrument reports)"), tr("Both"),
     tr("Instrument error")),
    (tr("All strips read / All patches read"), tr("Both"), tr("Measurement finished")),
]

#: Sounds that mark an event rather than a window.
EVENT_ROWS = [
    (tr("A patch was read and looks right"), tr("Patch by patch"), tr("Patch read OK")),
    (tr("A patch was read and looks off"), tr("Patch by patch"),
     tr("Patch reading looks off")),
    (tr("A strip was accepted"), tr("Strip reading"), tr("Strip read OK")),
    (tr("A strip was accepted but read quickly"), tr("Strip reading"), tr("Slow down")),
    (tr("The measurement finished"), tr("Both"), tr("Measurement finished")),
    (tr("A profile finished building"), tr("—"), tr("Profile build finished")),
]

#: Row 1 broken out: how a strip failure is classified, and the sound that
#: follows. Mirrors the wording tables in :mod:`core.measure_pace`.
FAILURE_ROWS = [
    (tr("Not enough samples per patch - Slow Down!"),
     tr("Too fast — ArgyllCMS says so itself"), tr("Slow down")),
    (tr("Reading is too short"),
     tr("Too fast — the whole swipe was over too quickly"), tr("Slow down")),
    (tr("Not enough patches"),
     tr("Too fast — the patches were too short in readings to tell apart"),
     tr("Slow down")),
    (tr("Too many patches"),
     tr("Hesitant, not hurried — extra transitions were found, so telling you to "
     "slow down would be exactly the wrong advice"), tr("Strip read failed")),
    (tr("Swipe didn't start and end on the media"), tr("Positioning, not speed"),
     tr("Strip read failed")),
    (tr("Light level is too low / too high"),
     tr("The instrument or the sheet, not speed"), tr("Strip read failed")),
    (tr("Reading is inconsistent"),
     tr("Uneven rather than simply quick — blaming speed could send you the wrong "
     "way"), tr("Strip read failed")),
]


def _esc(text: str) -> str:
    return html.escape(tr(text), quote=False)


def _table(headings, rows) -> str:
    out = ['<table border="1" cellspacing="0" cellpadding="6">',
           "<tr>" + "".join(f"<th>{_esc(h)}</th>" for h in headings) + "</tr>"]
    for n, row in enumerate(rows, start=1):
        cells = "".join(f"<td>{_esc(c)}</td>" for c in row)
        out.append(f"<tr><td>{n}</td>{cells}</tr>")
    out.append("</table>")
    return "\n".join(out)


def windows_and_sounds_html() -> str:
    """The tables as HTML, built from the rows above.

    :class:`ui.tooltip_button.TooltipButton` switches to rich text when a body
    contains a table.
    """
    return "\n\n".join([
        "<p>" + _esc(
            "Every window a measurement can raise, and the sound played as it "
            "opens — not when you answer it. The names in the sound columns "
            "are the ones in Preferences → Sounds, so you can change any of "
            "them there.") + "</p>",
        _table(("#", "Window", "Reading mode", "Sound played when it opens"),
               WINDOW_ROWS),
        "<p><b>" + _esc("Sounds that are not windows") + "</b> — "
        + _esc("these mark an event as it happens.") + "</p>",
        _table(("#", "Event", "Reading mode", "Sound"), EVENT_ROWS),
        "<p><b>" + _esc("Row 1 in full.") + "</b> " + _esc(
            "A failed strip does not always mean the same thing, so ChromIQ "
            "reads ArgyllCMS's own wording and picks the sound that fits. Only "
            "a genuinely hurried scan is told to slow down: saying that to "
            "someone who hesitated, or whose instrument drifted off the strip, "
            "would send them the wrong way.") + "</p>",
        _table(("#", "What ArgyllCMS reports", "What it means", "Sound"),
               FAILURE_ROWS),
        "<p><b>" + _esc("Two things worth knowing.") + "</b> " + _esc(
            "The completion sound waits half a second so the last strip's own "
            "cue can finish first — they used to arrive on top of each other. "
            "And ChromIQ plays none of these while stock ArgyllCMS chartread "
            "is doing the reading: it beeps for itself there and cannot be "
            "silenced, so ChromIQ would only double every event. On ChromIQ's "
            "own reading engine, Argyll's beeps are silenced and these sounds "
            "are the only ones you hear.") + "</p>",
    ])
