"""Path spellings for assertions that are written with "/" (CI round 2).

Many tests assert that a recorded folder contains ``"/Q-New/runs/"``. The app
records native paths, so on Windows the same folder reads
``...\\Q-New\\runs\\...``. `slashed` turns a native spelling into the "/" one
the assertion is written in. Where ``os.sep`` is already "/" (macOS, Linux)
it returns its argument unchanged, so nothing a test checks there changes.
"""
from __future__ import annotations

import os

#: A folder cannot be made unwritable with chmod on Windows: it only sets the
#: read-only attribute, which folders ignore. The reason given by every skip
#: of a test that locks a folder that way.
CHMOD_CANNOT_LOCK_A_FOLDER = (
    "a folder cannot be made unwritable with chmod on Windows (it only sets "
    "the read-only attribute, which folders ignore)")


def slashed(s: "str | os.PathLike") -> str:
    """*s* with native separators spelled "/" (also the doubled backslash
    of a path inside JSON text). The identity on POSIX."""
    s = os.fspath(s)
    if os.sep == "/":
        return s
    return s.replace("\\\\", "/").replace("\\", "/")
