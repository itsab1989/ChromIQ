"""Final fix round, S-7 (review 13): comments and docs no longer say that the table drive's
package, folders or USB library are unused: since 4.3.45 the Measure tab's table panel drives
the table and writes its session folders."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = ("core/file_manager.py", "core/usb_library.py", "docs/dev_folder_layout.md",
         "workflow/i1io/table/__init__.py")
STALE = re.compile(r"not wired in yet|nothing writes (it|them|these) yet|nothing calls (it|them) "
                   r"yet|nothing in the app imports this package yet", re.I)


def test_no_file_says_the_table_drive_is_unused():
    found = []
    for rel in FILES:
        for n, line in enumerate((ROOT / rel).read_text(encoding="utf-8").splitlines(), 1):
            if STALE.search(line):
                found.append(f"{rel}:{n}: {line.strip()}")
    assert found == []


def test_the_folder_layout_names_who_writes_the_table_folders():
    text = (ROOT / "docs/dev_folder_layout.md").read_text(encoding="utf-8")
    assert "writes them since 4.3.45" in text and "old/i1io-table/<stamp>/" in text
