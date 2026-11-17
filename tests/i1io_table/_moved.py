"""Where the tester program's files live in the app (test support, not shipped).

The table modules came from chromiq-i1io-session 0.6.0 (``tools/i1io_session/`` on branch
``tester/i1io-session-0.6.0``). Its tests that need only the moved modules are ported here
VERBATIM; they read the package's source through ``PKG / "<tester file name>"``, which this
module answers with the app file that file became. Names of files that did not move (the
console program ``i1io_session.py``, ``i1io_part_c.py``, README, BYTES.md, ``bin/``) are not
answered: the tests that read them stayed with the tester (tests/i1io_table/test_guarantees_in_the_app.py
says which, and keeps their rules for the app's copies).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / "workflow" / "i1io" / "table"
SIMS = ROOT / "tests" / "i1io_table"

#: tester file name -> app file
MOVED = {
    "i1io_session_table.py": TABLE / "session_table.py",
    "i1io_geometry.py": TABLE / "geometry.py",
    "i1io_c_lines.py": TABLE / "lines.py",
    "i1io_scan.py": TABLE / "scan.py",
    "i1io_reader.py": TABLE / "reader.py",
    "i1io_session_sim.py": SIMS / "session_sim.py",
    "i1io_part_c_sim.py": SIMS / "part_c_sim.py",
}


class _Package:
    """``PKG / name`` and ``PKG.glob("*.py")`` as the tester's tests use them."""

    def __truediv__(self, name: str) -> Path:
        if name not in MOVED:
            raise FileNotFoundError(f"{name} did not move into the app")
        return MOVED[name]

    def glob(self, pattern: str):
        assert pattern == "*.py", pattern
        return sorted(MOVED.values())


PKG = _Package()
