"""Bold lead-ins in help text: ``**How it works:**`` in the source, bold in
every help window.

Knut, #182 5856723428 (2026-09-27): *"When you write a heading or a bold font to
indicate a new topic or section, that disappears in the app, but this should
be visible in the help windows, everywhere in the app. This increases the
readability considerably."*

THE MARK IS WRITTEN INTO THE TEXT, NOT GUESSED FROM IT. A help body opens many
paragraphs with a short phrase, and only some of those phrases name a topic:
"How the sheet is divided." does, "ColorMunki + rig only." and "Mutually
exclusive with Double density." do not, and nothing in the punctuation tells
them apart. So the author marks the lead-in, the translator carries the mark
into the translation (the key is the English WITH its marks), and a
translation without marks simply shows plain text.

Help bodies are prose and are shown as plain text everywhere else, so a stray
"<" in them must never become markup: :func:`to_html` escapes everything and
keeps the author's line breaks and spacing (``white-space: pre-wrap``), so a
marked body lays out exactly as the plain one did, only with its lead-ins in
bold. Anywhere a body can land that is not a help window, :func:`strip_markup`
removes the marks.
"""
from __future__ import annotations

import html
import re

MARK = "**"

#: One bold run: ``**`` + at least one character that is not a line break +
#: ``**``. Non-greedy, and never across a line, so an unmatched mark cannot
#: swallow a paragraph.
_BOLD_RE = re.compile(r"\*\*([^\n*][^\n]*?)\*\*")

#: One emphasised run, the older ``*surface*`` of a few parameter helps
#: (B8-1521): a single ``*`` after a space, a bracket or the start, then a
#: LETTER, up to a single ``*`` right after a letter and before a space or
#: punctuation, on one line. The letters on both ends are what keep ``L*``,
#: ``a*``, ``b*`` and ``(*.cal)`` out of it: every one of those has its
#: asterisk straight after a letter at the start, or a dot after it.
_EMPH_RE = re.compile(r"(?<![*\w])\*(?=[^\W\d_])([^*\n]+?)(?<=[^\W_])\*(?![*\w])")


def has_markup(text: str) -> bool:
    """True when *text* carries at least one bold or emphasised run."""
    return bool(text) and "*" in text and (
        _BOLD_RE.search(text) is not None or _EMPH_RE.search(text) is not None)


def strip_markup(text: str) -> str:
    """*text* with its bold marks removed, for anything that is not a help
    window (a log line, a PDF, a plain label)."""
    if not text or "*" not in text:
        return text
    return _EMPH_RE.sub(r"\1", _BOLD_RE.sub(r"\1", text))


def strip_bold(text: str) -> str:
    """*text* with only its ``**`` marks removed: the text as the em dash rule
    reads it (`scripts/em_dash_check.py`), where a ``*word*`` emphasis was
    already part of the frozen string."""
    if not text or MARK not in text:
        return text
    return _BOLD_RE.sub(r"\1", text)


def bold_runs(text: str) -> "list[str]":
    """The bold runs of *text*, in order (for tests and for width sums)."""
    return _BOLD_RE.findall(text or "")


def _escape_emph(text: str) -> str:
    """*text* HTML-escaped, with its emphasised runs in ``<i>``."""
    out = []
    pos = 0
    for m in _EMPH_RE.finditer(text):
        out.append(html.escape(text[pos:m.start()], quote=False))
        out.append("<i>" + html.escape(m.group(1), quote=False) + "</i>")
        pos = m.end()
    out.append(html.escape(text[pos:], quote=False))
    return "".join(out)


def escape_bold(text: str) -> str:
    """*text* HTML-escaped, with its bold runs in ``<b>`` and its emphasised
    runs in ``<i>``: for a renderer that builds its own paragraphs (the
    printed help cards) and only needs the inline part."""
    out = []
    pos = 0
    for m in _BOLD_RE.finditer(text):
        out.append(_escape_emph(text[pos:m.start()]))
        out.append("<b>" + _escape_emph(m.group(1)) + "</b>")
        pos = m.end()
    out.append(_escape_emph(text[pos:]))
    return "".join(out)


def to_html(text: str, *, already_html: bool = False) -> str:
    """*text* as rich text for a QLabel: every bold run in ``<b>``.

    Plain text (the usual case) is escaped and wrapped in a block that keeps
    its line breaks and spaces, so it wraps and aligns as the plain label did.
    *already_html* is for a body that is markup already (a help text carrying a
    table): only the marks are converted, nothing is escaped.
    """
    if already_html:
        return _EMPH_RE.sub(r"<i>\1</i>", _BOLD_RE.sub(r"<b>\1</b>", text))
    return ('<div style="white-space: pre-wrap;">' + escape_bold(text)
            + "</div>")
