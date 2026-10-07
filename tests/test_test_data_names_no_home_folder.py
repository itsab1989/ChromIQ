"""The repository is public: a measurement copied into tests/data must not
carry the home folder (the account name) of the computer it was made on.

Found in the beta-12 review: Basti's ET8550 verification sheet arrived with
its print record's ``profile_path`` naming the macOS account it was printed
from. The record is kept (the report reads it), with the account name
replaced by the placeholder ``user``. Binary files (ICC profiles embed their
measurement) are scanned too.
"""
from __future__ import annotations

import re
from pathlib import Path

DATA = Path(__file__).parent / "data"
_HOME = re.compile(rb"(?:/Users/|/home/|C:\\\\Users\\\\|C:\\Users\\)"
                   rb"([A-Za-z0-9._-]+)")
_PLACEHOLDERS = {b"user", b"Shared", b"me", b"runner", b"someone"}


def test_no_home_folder_in_test_data():
    found = []
    for path in sorted(DATA.rglob("*")):
        if not path.is_file():
            continue
        for m in _HOME.finditer(path.read_bytes()):
            if m.group(1) not in _PLACEHOLDERS:
                found.append(f"{path.relative_to(DATA)}: "
                             f"{m.group(0).decode('latin-1')}")
    assert found == [], "\n".join(found)
