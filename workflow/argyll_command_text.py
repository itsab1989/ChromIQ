"""The ArgyllCMS commands a module runs, written out as a person would type them.

The Build Profile tab's information boxes (a dpreview request, 2026-11-02:
*"It would be nice if we could get a record of the commands sent to
Argyll"*) show the command lines ChromIQ is about to run. They are built from
the SAME argument lists the run hands to ``ArgyllRunner`` (the builders in
``workflow/profile_builder.py``, ``printcal_runner.py``, ``applycal_runner.py``
and ``ti3_merge.py``); this module only turns such a list into text.

THE TEXT IS FOR A TERMINAL, AND FOR A NAMED ONE. On macOS and Linux every
argument is quoted for the POSIX shells (zsh, bash: ``shlex.quote``), so a
description with a space in it (``-D 'My Printer'``) pastes as one argument,
exactly as ChromIQ passes it. On Windows the quoting is written for
PowerShell, the terminal Windows opens by default: single quotes, which
PowerShell takes literally (``$``, backtick, ``&``, ``%`` included), with a
single quote inside doubled. It is NOT cmd's quoting (review round 1:
``subprocess.list2cmdline`` leaves ``& ^ %`` bare, and ``cd /d`` is a cmd-only
flag PowerShell rejects), and the Preferences tooltip says which shell it is
for on each platform.

The one exception is a placeholder (``<measurement>``), which stands for a
file nobody has chosen yet: quoting it would make it look like a real name.
"""
from __future__ import annotations

import os
import re
import shlex
from pathlib import Path
from typing import Iterable


def _windows() -> bool:
    return os.name == "nt"


def quote_arg(arg: str, placeholders: Iterable[str] = ()) -> str:
    """*arg* as the platform's shell needs to see it to pass it unchanged."""
    text = str(arg)
    if any(p and p in text for p in placeholders):
        return text
    if _windows():
        return powershell_quote(text)
    return shlex.quote(text)


#: What PowerShell reads as one plain word: letters, digits and a few signs
#: that mean nothing to it in the middle of an argument. A comma (an array),
#: ``@`` (splatting), ``$``, backtick, quotes, brackets, ``;``, ``&``, ``|``,
#: ``<``, ``>``, ``#`` and spaces all do, so anything else is quoted.
_PS_PLAIN = re.compile(r"[\w%+:./\\=-]+")
#: …and an argument that starts with ``-`` stays bare only when it is letters,
#: digits and dashes: Windows PowerShell 5.1 splits a bare ``-s1.0`` at the
#: dot when it hands it to a program (review round 2; the known
#: ``-Dmaven.test.skip=true`` bug). Quoted, it arrives whole in every version.
_PS_PLAIN_FLAG = re.compile(r"-[A-Za-z0-9-]*")
#: Every character PowerShell reads as a single quote: ASCII ' and the
#: typographic ones U+2018 to U+201B. Inside single quotes each is doubled.
_PS_SINGLE_QUOTES = "'\u2018\u2019\u201a\u201b"


def powershell_quote(text: str) -> str:
    """*text* as one literal PowerShell argument."""
    if text and _PS_PLAIN.fullmatch(text) and (
            not text.startswith("-") or _PS_PLAIN_FLAG.fullmatch(text)):
        return text
    return "'" + "".join(c * 2 if c in _PS_SINGLE_QUOTES else c
                         for c in text) + "'"


def command_line(tool: str, args: "list[str]",
                 placeholders: Iterable[str] = ()) -> str:
    """``tool`` followed by *args*, each quoted for the platform's shell.

    The tool is named bare (``colprof``, not ``/Applications/Argyll/bin/
    colprof``): ChromIQ starts it from the ArgyllCMS folder in Preferences,
    and the box would otherwise repeat that folder in front of every line.
    """
    ph = tuple(placeholders)
    return " ".join([tool] + [quote_arg(a, ph) for a in args])


def change_folder_line(folder: "Path | str",
                       placeholders: Iterable[str] = ()) -> str:
    """The ``cd`` a tool that takes a bare file name needs first."""
    target = quote_arg(str(folder), tuple(placeholders))
    if _windows():
        # PowerShell: `-LiteralPath`, because plain `cd` matches wildcards and
        # fails on a folder with [ or ] in its name (review round 2). It also
        # changes the drive, which cmd's `cd` needs `/d` for (PowerShell
        # refuses `/d`).
        return f"Set-Location -LiteralPath {target}"
    return f"cd {target}"


def program_example(path: "Path | str") -> str:
    """A program typed by its full path, as the platform's terminal needs it.

    PowerShell runs a QUOTED path only behind its call operator ``&``, and
    the default ``C:\\Program Files\\ArgyllCMS\\bin`` has a space in it."""
    quoted = quote_arg(str(path))
    if _windows() and quoted.startswith("'"):
        return "& " + quoted
    return quoted
