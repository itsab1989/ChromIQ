"""Build step 9: the table window and the table package are imported lazily (by START on an
i1iO 2 chart), so PyInstaller cannot find them by itself: all three specs name every module
(NEXT_STEPS.md, the packaging note of step 4/6)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / "workflow" / "i1io" / "table"


@pytest.mark.parametrize("spec", ["ChromIQ.spec", "ChromIQWin.spec", "ChromIQLinux.spec"])
def test_every_spec_names_the_window_and_every_table_module(spec):
    text = (ROOT / spec).read_text(encoding="utf-8")
    m = re.search(r"_I1IO_TABLE_HIDDENIMPORTS = \[(.*?)\]", text, re.S)
    assert m, spec
    named = set(re.findall(r"'([\w.]+)'", m.group(1)))
    want = {"ui.i1io_table_window", "workflow.i1io.table_settle", "workflow.i1io.table"}
    want |= {f"workflow.i1io.table.{p.stem}" for p in TABLE.glob("*.py") if p.stem != "__init__"}
    assert want <= named, sorted(want - named)
    assert "*_I1IO_TABLE_HIDDENIMPORTS," in text
