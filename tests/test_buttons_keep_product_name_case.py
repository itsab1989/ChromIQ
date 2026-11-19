"""SHOULD-B2 of the table safety review (2026-11-19): a product name keeps its case on a button.

ButtonFontFilter.fit paints every QPushButton in capitals, so the dual scan's model question
showed "I1PRO 2", which is not the instrument's name. A button whose label begins with a product
name written with a small first letter carries ``chromiq_keep_case`` and is painted as written.
"""
from __future__ import annotations

import re
from pathlib import Path

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QPushButton

from ui.widgets import KEEP_CASE_PROPERTY, ButtonFontFilter

ROOT = Path(__file__).resolve().parents[1]
#: product names written with a small first letter (X-Rite's i1 family)
LOWER_PRODUCT = re.compile(r"^i1[A-Z]")


def test_a_button_marked_keep_case_is_painted_as_written(qapp):
    b = QPushButton("i1Pro 2")
    b.setProperty(KEEP_CASE_PROPERTY, True)
    ButtonFontFilter.fit(b)
    assert b.font().capitalization() == QFont.Capitalization.MixedCase
    plain = QPushButton("Another instrument")
    ButtonFontFilter.fit(plain)
    assert plain.font().capitalization() == QFont.Capitalization.AllUppercase


def test_a_keep_case_button_is_as_wide_as_its_label_needs(qapp):
    from PyQt6.QtGui import QFontMetrics
    b = QPushButton("i1Pro 2")
    b.setProperty(KEEP_CASE_PROPERTY, True)
    ButtonFontFilter.fit(b)
    assert b.minimumWidth() >= QFontMetrics(b.font()).horizontalAdvance("i1Pro 2")


def test_every_button_labelled_with_an_i1_product_name_keeps_its_case():
    missing = []
    pat = re.compile(r"(\w+)\s*=\s*\w+\.addButton\(\s*tr\(\s*\"([^\"]+)\"|"
                     r"(\w+)\s*=\s*QPushButton\(\s*tr\(\s*\"([^\"]+)\"")
    for p in sorted((ROOT / "ui").rglob("*.py")):
        lines = p.read_text(encoding="utf-8").splitlines()
        for i, ln in enumerate(lines):
            m = pat.search(ln)
            if not m:
                continue
            var, label = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
            if not LOWER_PRODUCT.match(label):
                continue
            near = "\n".join(lines[i:i + 6])
            if f"{var}.setProperty(KEEP_CASE_PROPERTY, True)" not in near:
                missing.append(f"{p.relative_to(ROOT)}:{i + 1} {label!r}")
    assert missing == []


def test_the_dual_scan_model_question_marks_its_i1pro2_button():
    src = (ROOT / "ui/tabs/tab_measure.py").read_text(encoding="utf-8")
    i = src.index('b2 = box.addButton(tr("i1Pro 2")')
    assert "b2.setProperty(KEEP_CASE_PROPERTY, True)" in src[i:i + 400]
