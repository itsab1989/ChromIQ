"""A shipped ChromIQ ignores the profile engine's development switches.

The profile engine reads a few dozen environment variables while it is being
developed: tuning knobs (``CHROMIQ_A51_MU``, ``CHROMIQ_A88``, ...), the extra
switch list (``CHROMIQ_ENGINE_NEXT``), the thread count
(``CHROMIQ_ENGINE_THREADS``), the fit cache (``CHROMIQ_A21_FIT_CACHE``) and the
helper override (``CHROMIQ_GAMMAP``). They are read in about eighty places,
some at import time and some in the middle of a build.

A variable left over on a tester's machine would change a profile with no
visible sign, so a FROZEN build (the packaged app) removes every one of them
from its own process environment before the engine can read it. Removing them
from ``os.environ`` is the one central place: every reader in the engine, and
every helper process the engine starts, sees the cleaned environment, and no
reader has to remember to ask.

Run from source (development, the research batteries, the test suite, which
sets ``CHROMIQ_ENGINE_THREADS=1`` for itself) nothing is touched.

``tests/test_engine_env_overrides_are_ignored_when_frozen.py`` keeps the
pattern in step with the engine: every variable the engine reads must be
recognised here.
"""
from __future__ import annotations

import os
import re
import sys

from core.logger import get_logger

log = get_logger(__name__)

#: Named development overrides.
_NAMED = frozenset({
    "CHROMIQ_ENGINE_NEXT",       # extra engine switches
    "CHROMIQ_ENGINE_THREADS",    # thread count (the bytes do not depend on it)
    "CHROMIQ_GAMMAP",            # another gamut-mapping helper binary
})

#: The numbered knobs: CHROMIQ_A21_FIT_CACHE, CHROMIQ_A68, CHROMIQ_A84_KEEP...
_NUMBERED = re.compile(r"^CHROMIQ_A\d+[A-Z]?(?:_[A-Z0-9_]*)?$")


def is_engine_override(name: str) -> bool:
    """True when *name* is one of the profile engine's development
    environment variables."""
    return name in _NAMED or bool(_NUMBERED.match(name))


def is_frozen() -> bool:
    """True in a packaged (PyInstaller) build."""
    return bool(getattr(sys, "frozen", False))


def ignore_engine_overrides_when_frozen(environ=None) -> list[str]:
    """Remove every engine development variable from *environ* (default: this
    process's environment) when the app is a packaged build. Returns the
    names removed, sorted. Does nothing, and returns ``[]``, from source.

    Safe to call any number of times and from any place a build starts.
    """
    if not is_frozen():
        return []
    env = os.environ if environ is None else environ
    removed = sorted(k for k in list(env.keys()) if is_engine_override(k))
    for name in removed:
        try:
            del env[name]
        except KeyError:
            pass
    if removed:
        log.warning("ignored the profile engine's development variables in "
                    "this packaged build: %s", ", ".join(removed))
    return removed
