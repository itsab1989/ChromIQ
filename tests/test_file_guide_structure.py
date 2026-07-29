"""#130 (Knut, 2026-07-29): the folder guide gains a "Project File Structure"
diagram, and the card moves next to the other two orientation cards.

*"Move the card to be places third in the list of cards, next to 'Overview of
Main Actions'. Then, add before the first section 'Files Relating to Features', a
new section 'Project File Structure'. In that section, create a full hierarchical
overview of each folder and a brief explanation what is located in each folder.
The hierarchy of folders shall be shown with lines pointing from higher level to
next lower level folders (dotted lines?), like a diagram often will, so that the
hierarchy becomes clear. Make sure all lines and folders are aligned for the same
level of the hierarchy, so that it looks unified, orderly and nice."*

Alignment is the whole request, so it is measured rather than eyeballed: every
row at the same depth must start its name at the same column, and a level's
connector must continue only while that level still has entries to come.
"""
from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import core.file_manager as fmod                       # noqa: E402
import ui.file_guide as fg                             # noqa: E402


# ---- the diagram ---------------------------------------------------------
def test_every_level_starts_at_the_same_column():
    """"All lines and folders aligned for the same level of the hierarchy." A
    depth that starts one column off is exactly the ragged look he asked to
    avoid."""
    by_depth: dict[int, set[int]] = {}
    for (depth, _name, _m), (prefix, _n, _mm) in zip(fg._structure(),
                                                     fg.tree_rows()):
        by_depth.setdefault(depth, set()).add(len(prefix))
    for depth, widths in by_depth.items():
        assert len(widths) == 1, (
            f"depth {depth} starts at columns {sorted(widths)} — the rows at one "
            f"level must all begin in the same place")
    # …and each level is indented from the one above by exactly one piece.
    ordered = [next(iter(by_depth[d])) for d in sorted(by_depth)]
    steps = {b - a for a, b in zip(ordered, ordered[1:])}
    assert steps == {len(fg._TREE_PASS)}, \
        f"levels are not indented evenly: {ordered}"


def test_a_branch_that_has_ended_draws_no_line_under_it():
    """The fault in my first attempt: continuation lines ran on below a branch
    that had already had its last child, so the diagram claimed a hierarchy that
    was not there."""
    rows = fg._structure()
    drawn = fg.tree_rows()
    for i, (depth, name, _m) in enumerate(rows):
        prefix = drawn[i][0]
        for level in range(1, depth):
            piece = prefix[(level - 1) * len(fg._TREE_PASS):
                           level * len(fg._TREE_PASS)]
            has_more = any(rows[j][0] == level for j in range(i + 1, len(rows))
                           if all(rows[k][0] >= level
                                  for k in range(i + 1, j + 1)))
            expect = fg._TREE_PASS if has_more else fg._TREE_GAP
            assert piece == expect, (
                f"row {name!r}: level {level} draws {piece!r}, expected "
                f"{expect!r}")


def test_the_last_entry_at_each_level_closes_its_branch():
    rows = fg._structure()
    drawn = fg.tree_rows()
    for i, (depth, name, _m) in enumerate(rows):
        if depth == 0:
            assert drawn[i][0] == "", "the root carries no connector"
            continue
        tail = drawn[i][0][-len(fg._TREE_LAST):]
        is_last = not any(
            rows[j][0] == depth for j in range(i + 1, len(rows))
            if all(rows[k][0] >= depth for k in range(i + 1, j + 1)))
        assert tail == (fg._TREE_LAST if is_last else fg._TREE_BRANCH), \
            f"row {name!r} draws {tail!r}"


def test_the_connectors_are_equal_width_in_the_faces_the_card_asks_for():
    """The alignment rests entirely on all four pieces having the same advance.

    Measured in the families the card's stylesheet actually names. It must NOT be
    measured in the UI font: Inter draws "├─ " at 36 px and "   " at 13, which
    would stagger every level — which is exactly why the tree column names a
    monospace family instead of inheriting.
    """
    from PyQt6.QtGui import QFont, QFontInfo, QFontMetrics
    from PyQt6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    checked = 0
    for family in ("Menlo", "Monaco", "Courier New"):
        f = QFont(family)
        if QFontInfo(f).family().lower() != family.lower():
            continue                      # not installed here
        fm = QFontMetrics(f)
        for piece in (fg._TREE_BRANCH, fg._TREE_LAST, fg._TREE_PASS):
            assert fm.inFont(piece[0]), f"{piece[0]!r} missing from {family}"
        widths = {fm.horizontalAdvance(p) for p in
                  (fg._TREE_BRANCH, fg._TREE_LAST, fg._TREE_PASS, fg._TREE_GAP)}
        assert len(widths) == 1, \
            f"{family}: the connector pieces differ in width: {widths}"
        checked += 1
    assert checked, "none of the named monospace families is available to check"


def test_the_diagram_asks_for_a_monospace_family_the_hard_way():
    """Measured, not assumed: Qt's rich text leaves ``<code>`` in the UI font,
    which draws "├─ " at 35 px and "   " at 19 and staggers every level. Only a
    family named on the element itself is honoured — this is the check that
    caught the crooked first attempt, after rendering the card and looking at it.
    """
    from PyQt6.QtGui import QTextDocument
    from PyQt6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    widths = set()
    for piece in (fg._TREE_BRANCH, fg._TREE_LAST, fg._TREE_PASS, fg._TREE_GAP):
        doc = QTextDocument()
        doc.setHtml(f'<pre style="font-family:{fg._MONO}; margin:0">{piece}</pre>')
        widths.add(round(doc.idealWidth(), 1))
    assert len(widths) == 1, (
        f"as the card actually asks for it, the connector pieces measure "
        f"{sorted(widths)} — the diagram would be crooked")


def test_the_diagram_names_the_folders_chromiq_really_creates():
    """A hand-written diagram drifts from the code. These are the folder names
    ``core.file_manager`` builds paths from, so a rename there fails here."""
    drawn = {name.rstrip("/") for _p, name, _m in fg.tree_rows()}
    for const in (fmod.REPORTS_DIRNAME, fmod.EXPORTS_DIRNAME,
                  fmod.CACHE_DIRNAME, fmod.VERIFICATIONS_DIRNAME,
                  fmod.CHART_SNAPSHOT_DIRNAME):
        assert const in drawn, f"the diagram never mentions {const}/"
    for expected in ("runs", "run1", "cal", "reads", "old", "project.json"):
        assert expected in drawn, f"the diagram never mentions {expected}"


def test_every_row_explains_itself():
    for _p, name, meaning in fg.tree_rows():
        assert meaning and len(meaning) > 30, f"{name} has no real explanation"
        assert "(s)" not in meaning


# ---- where it appears ----------------------------------------------------
def test_the_section_comes_before_the_features_section():
    html = fg.file_guide_html()
    assert "Project File Structure" in html
    assert html.index("Project File Structure") < \
        html.index("Files Relating to Features")


def test_the_text_sidecar_carries_the_same_diagram():
    """The guide is also dropped into every project folder, and a text file is
    already monospace — so the same rows are written there, unadorned."""
    body = fg.file_guide_body()
    assert "PROJECT FILE STRUCTURE" in body
    assert body.index("PROJECT FILE STRUCTURE") < \
        body.index("FILES RELATING TO FEATURES")
    for line in body.splitlines():
        if "verifications/" in line and line.startswith(" "):
            assert fg._TREE_BRANCH in line or fg._TREE_LAST in line
            break
    else:
        pytest.fail("the tree never reached the text sidecar")


def test_every_drawn_line_puts_its_text_in_the_same_column():
    """One column for the tree, one for the words, in the card and the sidecar
    alike — they share the renderer."""
    column = fg.tree_text_column()
    for line in fg.tree_lines():
        assert line[column:column + 1].strip(), \
            f"nothing in the text column of {line!r}"
        assert line[column - 1] == " ", f"no air before the text in {line!r}"


def test_a_wrapped_explanation_keeps_the_vertical_lines_unbroken():
    """The reason the text is wrapped here rather than by the renderer: in a
    table each row is as tall as its own text, so consecutive ``│`` glyphs do not
    meet and the verticals come out dashed. A continuation line carries the
    levels that are still open, and drops the branch mark — the words belong to
    the row above, not to a new entry."""
    rows = fg.tree_rows()
    lines = fg.tree_lines()
    assert len(lines) > len(rows), "nothing wrapped, so nothing is proven"
    drawn = {prefix + name for prefix, name, _m in rows}
    for line in lines:
        head = line.split("  ")[0]
        if head in drawn:
            continue                       # a row's own first line
        # a continuation: only connectors and spaces before the text
        assert set(head) <= {" "} | set("│"), \
            f"a continuation line carries a branch mark: {line!r}"
    # …and the level that is still open really is drawn on the line below.
    joined = "\n".join(lines)
    assert "│  └─" in joined or "│     " in joined


def test_the_text_sidecar_and_the_card_draw_the_same_diagram():
    body = fg.file_guide_body()
    for line in fg.tree_lines():
        assert line in body, f"the sidecar is missing {line[:40]!r}"


def test_the_card_sits_third_in_the_grid():
    """*"Move the card to be places third in the list of cards, next to
    'Overview of Main Actions'."*"""
    from ui.dialogs.welcome_dialog import WORKFLOWS
    keys = [w.get("key") for w in WORKFLOWS]
    assert keys[:3] == ["getting_started", "main_actions", "file_guide"], keys


def test_the_card_renders_the_diagram_pre_formatted():
    """HTML collapses runs of spaces, which would undo every bit of the
    alignment, so the diagram goes in a <pre> block."""
    html = fg.file_guide_html()
    body = html[html.index("Project File Structure"):]
    assert "<pre" in body
    pre = body[body.index("<pre"):body.index("</pre>")]
    assert fg._MONO in pre, "the block does not ask for a monospace family"
    import html as _html
    for line in fg.tree_lines()[:6]:
        assert _html.escape(line) in pre, f"missing from the block: {line[:40]!r}"
