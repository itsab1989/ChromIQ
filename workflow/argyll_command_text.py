"""The ArgyllCMS commands a module runs, written out as a person would type them.

The Build Profile tab's information boxes (a dpreview request, 2026-11-02:
*"It would be nice if we could get a record of the commands sent to
Argyll"*) show the command lines ChromIQ is about to run. They are built from
the SAME argument lists the run hands to ``ArgyllRunner`` (the builders in
``workflow/profile_builder.py``, ``printcal_runner.py``, ``applycal_runner.py``
and ``ti3_merge.py``); this module only turns such a list into text.

THE TEXT IS FOR A TERMINAL. Every argument is quoted the way the platform's
shell needs it, so a description with a space in it (``-D 'My Printer'``)
pastes as one argument, exactly as ChromIQ passes it. The one exception is a
placeholder (``<measurement>``), which stands for a file nobody has chosen
yet: quoting it would make it look like a real name.
"""
from __future__ import annotations

import os
import shlex
import subprocess
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
        return subprocess.list2cmdline([text])
    return shlex.quote(text)


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
    return f"cd /d {target}" if _windows() else f"cd {target}"
