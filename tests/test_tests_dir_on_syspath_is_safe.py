"""``tests/`` is on ``sys.path``, so no test module may shadow a real one.

#138 put this directory on ``sys.path`` so helpers beside the tests import by
bare name (``import _fontcheck``). That is convenient and it is also a trap: at
position 0, **every** module in here is importable by its bare name, so a test
file called ``types.py`` or ``yaml.py`` would silently shadow the real one for
the entire run — and the failure would look like anything except its cause.

327 files is too many to keep in one's head, so this holds the line instead.
"""
from __future__ import annotations

import pathlib
import sys


def _test_module_names() -> set[str]:
    here = pathlib.Path(__file__).resolve().parent
    return {p.stem for p in here.glob("*.py")}


def test_no_test_module_shadows_the_standard_library():
    clash = sorted(_test_module_names() & set(sys.stdlib_module_names))
    assert not clash, (
        "these files shadow standard-library modules for the whole test run: "
        + ", ".join(clash))


def test_no_test_module_shadows_an_installed_package():
    import importlib.metadata as md

    tops: set[str] = set()
    for dist in md.distributions():
        for f in (dist.files or []):
            parts = str(f).split("/")
            if len(parts) > 1 and parts[0].isidentifier():
                tops.add(parts[0])
    clash = sorted(_test_module_names() & tops)
    assert not clash, (
        "these files shadow installed packages for the whole test run: "
        + ", ".join(clash))


def test_the_helper_it_was_added_for_still_imports():
    import _fontcheck

    assert hasattr(_fontcheck, "skip_without_fonts")
    assert hasattr(_fontcheck, "skip_without_family")
