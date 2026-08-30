"""The "Keyboard shortcuts" Help card (Knut/Sebastian keyboard-accessibility
pass).

A single source of truth for the shortcut list shown in the Welcome/Help window,
kept in sync with the bindings installed in ``ui.main_window._install_shortcuts``
and the chart layout editor. Rows are listed alphabetically by what they do, as
Knut asked.

EVERY key name here must be built for the platform the user is on. The bindings
below render through ``QKeySequence(...).toString(NativeText)``, which gives ⌘⇧O
on macOS and Ctrl+Shift+O on Windows and Linux — so never hard-code a ⌘ or a ⇧
into a string. The hand-written rows use ``_shift()`` / ``_enter()`` for the
same reason (Knut, 4.1.3-beta.15: *"make sure tool tip text is specific to the
platform used, so that correct symbol or key is shown"*).

Every shortcut carries a modifier or is an F-key on purpose: during a measurement the
Measure tab claims the bare keys (Space, ← / →, Enter, Esc) to drive the
instrument, so nothing here can be stolen out from under chartread.
"""
from __future__ import annotations

import sys as _sys

import html

from core.i18n import tr


def keyboard_card_title() -> str:
    return tr("Keyboard shortcuts")


def keyboard_card_subtitle() -> str:
    # TRUTHFUL, not tidy. The card carries two tables: the application
    # shortcuts, sorted alphabetically by what they do, and the measuring keys,
    # which are in the order you use them. Knut read the old subtitle as a
    # promise about both and found the second one unsorted (#164) — sorting it
    # would scatter the reading sequence, so the sentence is what changes.
    return tr("Every keyboard shortcut in ChromIQ: the general ones "
              "alphabetically, then the measuring keys in the order you use "
              "them.")


def keys(spec: str) -> str:
    """A shortcut written the way THIS platform writes it.

    The card used to spell every shortcut with the macOS glyphs — ⌘1, ⌘⇧Z —
    which is simply wrong on Windows and Linux, where the same binding is
    Ctrl+1 and Ctrl+Shift+Z (#164, Knut: *"make sure symbols used for macOS is
    shown correctly for Linux or Windows"*). The bindings themselves are
    declared as ``Ctrl+…`` in ui/main_window.py; Qt already knows how to say
    that in the local idiom, so it is asked rather than second-guessed.
    """
    from PyQt6.QtGui import QKeySequence
    return QKeySequence(spec).toString(QKeySequence.SequenceFormat.NativeText)


#: action id → QKeySequence spec. THE ONLY PLACE A BINDING IS WRITTEN DOWN.
#: `ui.main_window` installs from here, the Help card lists from here, and a
#: tooltip asks for its key from here — so the three cannot disagree. Before
#: this, the bindings were typed as literals in `_install_shortcuts` AND again
#: in `_shortcuts()`, and a third copy for tooltips would have made three.
BINDINGS: dict[str, str] = {
    "open_project":       "Ctrl+O",
    "open_chart_file":    "Ctrl+Shift+O",
    "preferences":        "Ctrl+,",
    "tools":              "Ctrl+T",
    "help":               "F1",
    "help_alt":           "Ctrl+?",
    "primary_action":     "Ctrl+Return",
    "primary_action_alt": "Ctrl+Enter",
    "undo":               "Ctrl+Z",
    "redo":               "Ctrl+Shift+Z",
    "redo_alt":           "Ctrl+Y",
    **{f"tab_{i}": f"Ctrl+{i}" for i in range(1, 6)},
}


def keys_for(action: str) -> str:
    """The platform's spelling of one binding, or "" when it has none."""
    spec = BINDINGS.get(action)
    return keys(spec) if spec else ""


def with_shortcut(tooltip: str, action: str) -> str:
    """*tooltip* with its shortcut in parentheses on the FIRST line (Knut).

    The parentheses and the glyph are added AFTER ``tr()``, never inside a
    translatable string — so no catalogue can carry a stale "⌘O" the way
    `welcome_dialog` did, and Windows and Linux get "Ctrl+O" from the same one
    key. A tooltip whose first line is the button's name reads
    "Open Project (⌘O)"; the explanation below it is untouched.
    """
    k = keys_for(action)
    if not k:
        return tooltip
    head, sep, rest = (tooltip or "").partition("\n")
    return f"{head} ({k}){sep}{rest}"


_IS_MAC = _sys.platform == "darwin"


def _shift() -> str:
    """"⇧" on macOS, the localized "Shift" everywhere else.

    Follows the ruling already made for the layout editor's selection hints
    (`ui/dialogs/ti2_relayout_dialog.py:455-464`), so the two agree.
    """
    return "⇧" if _IS_MAC else tr("Shift")


def _enter() -> str:
    """"⏎" on macOS, the localized "Enter" everywhere else."""
    return "⏎" if _IS_MAC else tr("Enter")


def attach_shortcut_hint(widget, action: str) -> None:
    """Give a button its shortcut hint, inventing a tooltip from its own label
    when it has none. ``widget.text()`` is already translated, so this adds no
    new key to any catalogue.

    Calling it twice on the same widget is a no-op, not "Generate Chart (⌘↵)
    (⌘↵)": it reads back `widget.toolTip()`, so without the check a second call
    — a re-styled tab, a rebuilt row — would append the hint again.
    """
    try:
        k = keys_for(action)
        tip = widget.toolTip() or widget.text().replace("\n", " ").replace("&", "")
        if k and f"({k})" in tip:
            return                      # already carries it — do not append twice
        widget.setToolTip(with_shortcut(tip, action))
    except Exception:      # noqa: BLE001 — a tooltip is never worth a crash
        pass


def _shortcuts() -> list[tuple[str, str]]:
    """(keys, what-it-does) — the second field is what the list is sorted by."""
    return [
        (keys_for("open_project"), tr("Open a profile project")),
        (keys_for("open_chart_file"), tr("Open a chart file (.ti2)")),
        (f"{keys_for("tab_1")} … {keys_for("tab_5")}",
         tr("Go to a tab (1 Create Chart · 2 Print Chart · 3 Measure · "
            "4 Build Profile · 5 Check & Refine)")),
        ("← / →", tr("Move between tabs (when the tab strip has focus — e.g. "
                     "right after {first}–{last})").format(
                         first=keys_for("tab_1"), last=keys_for("tab_5"))),
        (f"F1  ·  {keys_for("help_alt")}", tr("Open Help (this window)")),
        (keys_for("preferences"), tr("Open Preferences (Settings)")),
        (keys_for("tools"), tr("Open the Tools menu")),
        (f"{keys_for("redo")}  ·  {keys_for("redo_alt")}",
         tr("Redo — in the chart layout editor")),
        (keys_for("primary_action"),
         tr("Run the current tab's main action (Generate · Print · "
            "Measure · Build · Check)")),
        (keys_for("undo"), tr("Undo — in the chart layout editor")),
    ]


def _modifier_note() -> str:
    """Name the modifier key in the platform's own words, or say nothing.

    macOS spells it with a symbol that wants explaining; Windows and Linux
    spell it "Ctrl", which does not.
    """
    import sys
    if sys.platform == "darwin":
        return tr("On macOS ⌘ is the Command key.")
    return ""


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
        return tr("ChromIQ engine")
    return tr("Both engines")


def _measurement_keys() -> list[tuple[str, str, str]]:
    """(keys, what-it-does, which reader) for the keys that drive a read."""
    return [
        (tr("Instrument button  ·  {enter}  ·  any key").format(enter=_enter()),
         tr("Start reading the strip or patch you have been asked for."),
         BOTH),
        (_enter(),
         tr("At a warning — “this looks like the wrong strip”, “unexpected "
            "colour response” — keep the reading anyway."),
         BOTH),
        (tr("Space  ·  R"),
         tr("At a warning or a failure, throw the reading away and try the "
            "same strip again. This is what the Retry button sends."),
         BOTH),
        (tr("Space  ·  {enter}").format(enter=_enter()),
         tr("CR30 only, while it is waiting for a patch: take the reading "
            "without touching the instrument, so it stays perfectly still. "
            "Steadier than pressing the instrument's own button, which moves "
            "it by about ten times its own measurement noise. Offered once "
            "ChromIQ has learned that instrument's white tile."),
         CHROMIQ),
        ("F  ·  B",
         tr("Move one strip forward or back."),
         BOTH),
        ("{s}F  ·  {s}B".format(s=_shift()),
         tr("Move ten strips at a time. ArgyllCMS chartread does this itself; "
            "the ChromIQ engine is sent ten single steps instead, which comes "
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
            "Needs the ChromIQ engine, which can be told where to go."),
         CHROMIQ),
        ("D",
         tr("Finish: write what has been measured so far and end the "
            "measurement. If any patches are still unread you are asked to "
            "confirm first."),
         BOTH),
        (tr("Esc  ·  Q"),
         tr("Give up — and the two engines differ here, which is worth "
            "knowing before you press it. ArgyllCMS chartread throws away "
            "everything you measured; the ChromIQ engine writes it out "
            "first. If you want to keep your readings, press Stop instead of "
            "Esc: Stop always offers to save them, whichever engine is "
            "running."),
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
        f"{esc(_modifier_note())}</p>",
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
        f"<th align='left'>{esc(tr('Which engine'))}</th></tr>")
    for keys, action, which in _measurement_keys():
        parts.append(
            "<tr>"
            f"<td valign='top'><code>{esc(keys)}</code></td>"
            f"<td valign='top'>{esc(action)}</td>"
            f"<td valign='top'>{esc(_reader_label(which))}</td></tr>")
    parts.append("</table>")
    parts.append(
        f"<p style='margin-top:12px'>{esc(tr('You can change which engine ChromIQ uses in Preferences → Beta.'))}</p>")
    return "".join(parts)
