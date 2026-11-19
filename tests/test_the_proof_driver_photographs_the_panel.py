"""4.3.49 safety review 449, SHOULD-7: the driven-instrument proof template photographed the
table's question pages as the MAIN window (which showed the Create Chart tab), so the pictures
did not show the pages they were named after. Every picture of a panel page goes through
``pshot``, which photographs the panel's own top-level window."""
from __future__ import annotations

import re
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "scripts"
       / "driven_instrument_proof_driver.py").read_text(encoding="utf-8")


def test_pshot_photographs_the_panels_own_window():
    body = SRC[SRC.index("def pshot("):SRC.index("def panel(")]
    assert "w.window()" in body


def test_every_page_of_the_panel_is_photographed_as_the_panel():
    answer = SRC[SRC.index("def answer(w, page):"):SRC.index("def drive_until(")]
    assert "pshot(w," in answer and re.search(r"(?<!p)shot\(", answer) is None
    # only the Create Chart tab and the Measure tab after Save are main-window pictures
    plain = re.findall(r'(?<![p\w])shot\("([\w-]+)"', SRC)
    assert set(plain) <= {"00-create-chart", "after-save"}, plain
