"""The "Keyboard shortcuts" Help card (Knut/Sebastian keyboard-accessibility
pass).

A single source of truth for the shortcut list shown in the Welcome/Help window,
kept in sync with the bindings installed in ``ui.main_window._install_shortcuts``
and the chart layout editor. Rows are listed alphabetically by what they do, as
Knut asked.

Symbols use the macOS convention (⌘ = Command, ⇧ = Shift, ⏎ = Return). Every
shortcut carries a modifier or is an F-key on purpose: during a measurement the
Measure tab claims the bare keys (Space, ← / →, Enter, Esc) to drive the
instrument, so nothing here can be stolen out from under chartread.
"""
from __future__ import annotations

import html

from core.i18n import tr


def keyboard_card_title() -> str:
    return tr("Keyboard shortcuts")


def keyboard_card_subtitle() -> str:
    return tr("Every keyboard shortcut in ChromIQ, listed alphabetically.")


def _shortcuts() -> list[tuple[str, str]]:
    """(keys, what-it-does) — the second field is what the list is sorted by."""
    return [
        ("⌘1 … ⌘5",
         tr("Go to a tab (1 Create Chart · 2 Print Chart · 3 Measure · "
            "4 Build Profile · 5 Check & Refine)")),
        ("← / →", tr("Move between tabs (when the tab strip has focus — e.g. "
                     "right after ⌘1–5)")),
        ("F1  ·  ⌘?", tr("Open Help (this window)")),
        ("⌘,", tr("Open Preferences (Settings)")),
        ("⌘T", tr("Open the Tools menu")),
        ("⌘⇧Z  ·  ⌘Y", tr("Redo — in the chart layout editor")),
        ("⌘⏎",
         tr("Run the current tab's main action (Generate · Print · "
            "Measure · Build · Check)")),
        ("⌘Z", tr("Undo — in the chart layout editor")),
    ]


def _measurement_note() -> str:
    return tr(
        "While you are measuring a chart the keyboard drives the instrument "
        "instead, so every shortcut above pauses until the measurement is "
        "finished. These are the keys it listens for.")


#: Which reader a measurement key applies to. ChromIQ can read a chart with
#: ArgyllCMS's own chartread or with its own helper (Preferences → Beta), and a
#: few keys genuinely differ between them — Knut asked for the difference to be
#: on the card rather than in a release note.
BOTH = "both"
STOCK = "argyll"
CHROMIQ = "chromiq"


def _reader_label(which: str) -> str:
    if which == STOCK:
        return tr("ArgyllCMS chartread")
    if which == CHROMIQ:
        return tr("ChromIQ reader")
    return tr("Both readers")


def _measurement_keys() -> list[tuple[str, str, str]]:
    """(keys, what-it-does, which reader) for the keys that drive a read."""
    return [
        (tr("Instrument button  ·  ⏎  ·  any key"),
         tr("Start reading the strip or patch you have been asked for."),
         BOTH),
        ("⏎",
         tr("At a warning — “this looks like the wrong strip”, “unexpected "
            "colour response” — keep the reading anyway."),
         BOTH),
        (tr("Space  ·  R"),
         tr("At a warning or a failure, throw the reading away and try the "
            "same strip again. This is what the Retry button sends."),
         BOTH),
        ("F  ·  B",
         tr("Move one strip forward or back."),
         BOTH),
        (tr("⇧F  ·  ⇧B"),
         tr("Move ten strips at a time. ArgyllCMS chartread does this itself; "
            "the ChromIQ reader is sent ten single steps instead, which comes "
            "to the same move."),
         BOTH),
        ("←  ·  →",
         tr("The same as B and F — one strip back or forward."),
         BOTH),
        ("N",
         tr("Jump to the next strip that has not been read yet."),
         BOTH),
        ("S",
         tr("Skip the strip or patch that just failed and carry on with the "
            "next one."),
         BOTH),
        (tr("Click a strip in the preview"),
         tr("Jump straight to that strip — handy for measuring one again. "
            "Needs the ChromIQ reader, which can be told where to go."),
         CHROMIQ),
        ("D",
         tr("Finish: write what has been measured so far and close the "
            "reader. You are asked to confirm if patches are still unread."),
         BOTH),
        (tr("Esc  ·  Q"),
         tr("Give up. WITH ONE IMPORTANT DIFFERENCE: ArgyllCMS chartread "
            "throws away everything you measured, while the ChromIQ reader "
            "writes it out first. Use Stop rather than Esc if you want to "
            "keep your readings whichever reader is running — Stop always "
            "offers to save them."),
         BOTH),
    ]


def keyboard_shortcuts_html() -> str:
    """Rich-text (HTML) table for the Welcome/Help card, mirroring the folder
    guide's theme-neutral styling (grey header row, body inherits the label's
    themed text colour)."""
    def esc(s: str) -> str:
        return html.escape(s)

    parts = [
        f"<p>{esc(tr('Shortcuts for getting around ChromIQ with the keyboard. '))}"
        f"{esc(tr('On macOS ⌘ is the Command key.'))}</p>",
        "<p style='font-size:5px; margin:0'>&nbsp;</p>",
        "<table cellspacing='0' cellpadding='4' width='100%' "
        "style='border-collapse:collapse'>",
        "<tr style='color:#888'>"
        f"<th align='left'>{esc(tr('Shortcut'))}</th>"
        f"<th align='left'>{esc(tr('What it does'))}</th></tr>",
    ]
    for keys, action in sorted(_shortcuts(), key=lambda r: r[1].lower()):
        parts.append(
            "<tr>"
            f"<td valign='top'><code>{esc(keys)}</code></td>"
            f"<td valign='top'>{esc(action)}</td></tr>")
    parts.append("</table>")

    # While you are measuring — its own table, because the keys are different
    # and because a couple of them depend on which reader is running.
    parts.append(
        f"<p style='margin-top:18px'><b>{esc(tr('While you are measuring'))}"
        f"</b></p>")
    parts.append(f"<p>{esc(_measurement_note())}</p>")
    parts.append("<p style='font-size:5px; margin:0'>&nbsp;</p>")
    parts.append(
        "<table cellspacing='0' cellpadding='4' width='100%' "
        "style='border-collapse:collapse'>")
    parts.append(
        "<tr style='color:#888'>"
        f"<th align='left'>{esc(tr('Key'))}</th>"
        f"<th align='left'>{esc(tr('What it does'))}</th>"
        f"<th align='left'>{esc(tr('Which reader'))}</th></tr>")
    for keys, action, which in _measurement_keys():
        parts.append(
            "<tr>"
            f"<td valign='top'><code>{esc(keys)}</code></td>"
            f"<td valign='top'>{esc(action)}</td>"
            f"<td valign='top'>{esc(_reader_label(which))}</td></tr>")
    parts.append("</table>")
    parts.append(
        f"<p style='margin-top:12px'>{esc(tr('You can change which reader ChromIQ uses in Preferences → Beta features.'))}</p>")
    return "".join(parts)
