"""How long a project name may be before its own files stop fitting — Windows.

THE CAP WAS 120 UTF-8 BYTES AND IT WAS THE WRONG QUESTION. That number was
chosen on macOS, where the limit is per *name component*: 255 bytes, so 120
left generous room for the suffixes ChromIQ appends. Windows limits the whole
**path** instead, to ``MAX_PATH``, and nothing checked that. Measured on a
Windows 11 VM on 2026-09-03 (``WINDOWS-VM-REPORT.md`` §B), at a project root
of the same length as the real default::

     name  chart path len  validate  chart file writes?
      110             258        OK   yes
      111             260        OK   NO [2] No such file or directory
      120             278        OK   NO [2] No such file or directory

The person is told nothing. The name is accepted, the project folder is
created, and the chart build then dies with a file-not-found naming a path
that looks perfectly ordinary.

The budget, and where every number in it comes from
--------------------------------------------------

**259 characters** is the longest path Windows will open with ``MAX_PATH`` in
force. ``MAX_PATH`` is 260 *including* the terminating NUL, so 259 is usable.
The VM stepped in twos and measured 258 writing and 260 failing; 259 itself is
the documented limit rather than a measured one, and it is the generous end,
so nothing here depends on it.

**The name appears TWICE** in the paths that matter — once as the project
folder and once as the file stem inside it — so every character of the name
costs two characters of path. That is not an accident to be fixed: the stem is
the project name on purpose, so printtarg stamps it on the printed sheet and
the built ICC is self-identifying (see ``core.file_manager.Run.stem``).

**61 characters** is the longest constant part. It was not guessed: every
path-valued property of ``Run``, ``Calibration`` and ``Verification`` was
enumerated with a marker name and sorted by what remained. The worst is the
file a rename moves aside when something already holds the name it needs::

    <root>\\<name>\\runs\\run99\\<name>_conflicted_at_renaming_procedure_9.channels.json
           \\_____/\\__________/\\_____/\\_________________________________________________/
             name    12 chars    name                    49 chars

and the worst that appears in an ordinary session, four characters shorter, is
a verification measurement::

    <root>\\<name>\\runs\\run99\\verifications\\2026-09-03_120000_9\\<name>-verify.ti3

Two things are deliberately NOT budgeted for, because each would cost every
user two more characters of name to cover a case that is already handled: a
project with more than 99 runs, and more than nine verifications inside one
second. Neither loses data if it is reached — ``_move_aside_conflict`` returns
None and the caller leaves everything as it was.

**37 characters** is the reference Windows root: ``C:\\Users\\`` (9) plus a
username of up to 20 characters plus ``\\ChromIQ`` (8). It is used on macOS and
Linux, where the *destination* root cannot be known.

    259 - 37 - 61 = 161 characters of path for two copies of the name
    161 // 2      = 80

So **80 characters**, and on Windows the real root is used instead of the
reference one, which gives less on a machine whose projects live somewhere
deep (``C:\\Users\\name\\OneDrive\\Documents\\ChromIQ`` is 44, and 77 characters
of name) and never more, so a name made on one Windows machine still fits on
another.

Why the cap is the same on macOS and Linux
------------------------------------------

For the reason ``ui.dialogs.name_prompt.RESERVED`` already gives about ``CON``
and ``PRN``: *"ChromIQ projects are copied between machines and shared, and a
folder that cannot be created on one of them is a trap the person springs
later, on somebody else's computer."* A 120-character project name made on a
Mac cannot be opened on Windows at all. The difference from the device names is
that the destination root is unknowable from here, which is what the reference
root is for.

The POSIX per-component rule has not gone away; it is simply no longer the
binding one. It stays at 120 UTF-8 BYTES, because a component limit is counted
in bytes and Windows counts characters — so a 78-character Japanese name is 78
against ``MAX_PATH`` and 234 bytes against the macOS limit, and only checking
both catches it.

A NAME ALREADY ON DISK IS A FIXED POINT
---------------------------------------

``core.file_manager.FileManager._sanitise`` does not cap a length, on purpose:
it is also the function that RESOLVES an existing folder, so a rule that
shortened a name would move somebody's existing project. Tightening a cap at
the door therefore cannot lock anyone out of a project they already have —
provided the door knows the difference. Names between 81 and 120 characters
exist in the wild, because ChromIQ made them. See ``name_prompt.validate``'s
``on_disk`` argument, which is how the door is told.
"""
from __future__ import annotations

import os
from pathlib import Path

#: The longest path Windows opens with MAX_PATH in force: MAX_PATH (260) minus
#: the terminating NUL.
WINDOWS_PATH_MAX = 259

#: How many times a project name appears in its own longest path — once as the
#: folder, once as the file stem inside it.
NAME_OCCURRENCES = 2

#: Everything in that path that is NOT the root and NOT the name. Derived by
#: enumerating every path property of Run / Calibration / Verification; see the
#: module docstring for the winner and for what is deliberately left out.
LONGEST_TAIL = 61

#: ``C:\Users\`` + a username of up to 20 characters + ``\ChromIQ``. Used where
#: the machine a project will be COPIED to cannot be known.
REFERENCE_WINDOWS_ROOT = 37

#: The POSIX per-component limit, unchanged from the rule this module replaces.
#: Bytes, because that is what a filesystem component limit counts.
MAX_NAME_BYTES = 120

#: Never propose a cap shorter than this, whatever the root. A root deep enough
#: to push below it is a root ChromIQ cannot work in at all, and saying "your
#: name may be four characters" would be a worse answer than saying nothing.
MIN_BUDGET = 24


def budget_for_root(root: "str | os.PathLike[str] | None") -> int:
    """The longest project name, in characters, whose paths fit under *root*.

    *root* is the folder projects are created in. ``None`` uses the reference
    Windows root, which is what every non-Windows machine gets.
    """
    n = REFERENCE_WINDOWS_ROOT if root is None else len(str(root))
    room = WINDOWS_PATH_MAX - n - LONGEST_TAIL
    return max(MIN_BUDGET, room // NAME_OCCURRENCES)


def name_budget(root: "str | os.PathLike[str] | None" = None) -> int:
    """The cap a new project name is held to, in characters.

    On Windows this is the smaller of what the machine's OWN root allows and
    what the reference root allows, so a name made on a shallow root still fits
    when the project is copied to a deeper one. Everywhere else it is the
    reference root alone, because the Windows machine a project may be copied
    to cannot be inspected from here.
    """
    portable = budget_for_root(None)
    if os.name != "nt":
        return portable
    if root is None:
        root = current_output_root()
        if root is None:
            return portable
    return min(portable, budget_for_root(root))


def current_output_root() -> "Path | None":
    """Where projects are created on THIS machine, or None if it cannot be
    asked.

    The same two-line rule as ``FileManager.root_dir``, without needing a
    ``FileManager``: `validate` is called from five name boxes and a build
    gate, and not all of them have one. Imported inside the function so this
    module stays free of Qt for the callers that only want the arithmetic —
    ``core.settings`` is a ``QSettings`` store.
    """
    try:
        from core.platform_paths import default_output_root
        from core.settings import AppSettings
        custom = AppSettings().get("custom_output_path", "")
        return Path(custom) if custom else default_output_root()
    except Exception:                # noqa: BLE001 — a cap must never raise
        return None


def fits(name: str, *, root: "str | os.PathLike[str] | None" = None) -> bool:
    """Whether *name* satisfies both length rules — Windows path and POSIX
    component."""
    return (len(name) <= name_budget(root)
            and len(name.encode("utf-8")) <= MAX_NAME_BYTES)


def longest_prefix_that_fits(name: str,
                             *, root: "str | os.PathLike[str] | None" = None
                             ) -> int:
    """How many characters of *name* would fit — the number to put in a message.

    ONE NUMBER, ALWAYS ACTIONABLE. There are two rules and they are counted in
    different units, so naming either one on its own can be wrong: told "80
    characters" a Japanese name of 80 characters still fails the byte rule, and
    told "120" a name that never touched the byte rule is misdirected. Cutting
    the name until it passes both answers the only question the person has.
    """
    if fits(name, root=root):
        return len(name)
    k = len(name)
    while k and not fits(name[:k], root=root):
        k -= 1
    return k


def example_path(name: str,
                 root: "str | os.PathLike[str] | None" = None) -> Path:
    """The longest path *name* leads to under *root* — for a probe or a report,
    so the arithmetic above can be checked against a real string rather than
    believed."""
    base = Path(str(root) if root is not None else "C:\\Users\\reference\\ChromIQ")
    return (base / name / "runs" / "run99"
            / f"{name}_conflicted_at_renaming_procedure_9.channels.json")
