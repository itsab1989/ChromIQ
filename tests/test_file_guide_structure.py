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
import pathlib
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
    from _fontcheck import skip_without_fonts
    skip_without_fonts()                  # no fonts here → none to measure
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


# ---------------------------------------------------------------------------
# A VERTICAL MUST REACH THE CHILD IT POINTS AT (#164, Knut)
# ---------------------------------------------------------------------------
# *"the vertical lines going down from some folder names, for their
# sub-folders, has an empty gap from the parent folder name and down to its
# child folder name. Example is below run1/ and below verifications/."*
#
# The continuation lines carried every level open ABOVE a row but not the one
# opening AT it, so a folder with a two-line explanation had a gap before its
# first child and the diagram read as dashed.
#
# The test above this one — "a wrapped explanation keeps the vertical lines
# unbroken" — did NOT catch it: it asserts a continuation carries no BRANCH
# mark, never that the vertical actually reaches the child. Proven blind by
# running it against the fixed renderer, where it passed either way. This one
# is positional.


def _rows_with_children():
    from ui.file_guide import tree_rows

    rows = tree_rows()
    for i, (prefix, name, _m) in enumerate(rows):
        nxt = rows[i + 1][0] if i + 1 < len(rows) else ""
        if len(nxt) > len(prefix):
            yield i, prefix, name


def test_a_folder_with_children_carries_its_vertical_down_to_them():
    """For every row that opens a level, each of its continuation lines must
    have the connector at the column its children start in."""
    from ui.file_guide import _TREE_PASS, tree_lines, tree_rows, tree_text_column

    rows = tree_rows()
    lines = tree_lines(62)
    col = tree_text_column()
    # Walk the rendered lines alongside the rows that produced them.
    li = 0
    broken = []
    import textwrap
    for i, (prefix, name, meaning) in enumerate(rows):
        wrapped = textwrap.wrap(meaning, 62) or [""]
        head, conts = lines[li], lines[li + 1:li + len(wrapped)]
        li += len(wrapped)
        nxt = rows[i + 1][0] if i + 1 < len(rows) else ""
        if len(nxt) <= len(prefix):
            continue                            # no children: nothing to carry
        want = len(prefix)                      # the column the children sit at
        for c in conts:
            if c[want:want + len(_TREE_PASS)].rstrip() != _TREE_PASS.rstrip():
                broken.append(f"{(prefix + name).strip()!r}: {c[:col].rstrip()!r}")
    assert not broken, (
        "a folder's vertical does not reach its children:\n  "
        + "\n  ".join(broken))


def test_the_root_row_puts_its_vertical_at_column_zero():
    """The root has no prefix, so it opens no level ABOVE itself — appending a
    gap (as this used to) put its continuation three columns right of where its
    children actually sit."""
    from ui.file_guide import _TREE_PASS, tree_lines

    lines = tree_lines(62)
    assert lines[1].startswith(_TREE_PASS.rstrip()), (
        f"the root's continuation does not carry its vertical: {lines[1][:20]!r}")


# ---------------------------------------------------------------------------
# THE DIAGRAM FITS THE PAPER IN EVERY LANGUAGE (#164)
# ---------------------------------------------------------------------------
# A CJK ideograph is one character and TWO columns wide. `textwrap` counts
# characters, so the Japanese and Chinese folder guide was wrapped at 94
# characters and rendered 156 columns — 43 % of every long line outside the
# paper, and on the printed card 156 × 1.905 mm is the full width of an A4
# sheet, so the right-hand column simply ran off it.


def _budget():
    from ui.file_guide import tree_text_column
    return tree_text_column() + 62


@pytest.mark.parametrize("code", [p.stem for p in
                                  sorted((pathlib.Path(__file__).resolve().parent.parent
                                          / "data" / "i18n").glob("*.json"))]
                                 + ["en"])
def test_no_line_runs_past_the_paper_in_any_language(code):
    from core.i18n import set_language
    from ui.file_guide import _display_width, tree_lines

    try:
        set_language(code)
        widest = max(_display_width(line) for line in tree_lines(62))
        assert widest <= _budget(), (
            f"{code}: the widest line is {widest} display columns against a "
            f"{_budget()}-column page — it runs off the paper")
    finally:
        set_language("en")


def test_a_narrow_language_is_wrapped_exactly_as_before():
    """The eleven languages with no wide characters must be untouched — and by
    CONSTRUCTION, not by luck: `_wrap_display` falls straight through to
    `textwrap` when every character is one column, so the new branch is never
    entered for them."""
    import textwrap

    from core.i18n import set_language
    from ui.file_guide import _wrap_display, tree_rows

    try:
        for code in ("en", "de", "fr", "ru", "pl"):
            set_language(code)
            for _prefix, _name, meaning in tree_rows():
                assert _wrap_display(meaning, 62) == (
                    textwrap.wrap(meaning, 62) or [""]), (
                    f"{code}: wrapping changed for a language with no wide "
                    "characters")
    finally:
        set_language("en")


def test_punctuation_does_not_open_a_line():
    """A closing bracket, comma or dash stranded at the left margin reads as a
    typo — "kinsoku shori" reduced to the rule that matters here.

    THE PREVIOUS VERSION OF THIS TEST COULD NOT FAIL. It sliced with
    ``line[len(line) - len(line.lstrip()):]``, which is just ``lstrip()``, so
    the character it checked was always the tree-art glyph (``|``, ``+``) and
    never a text character. Real violations shipped green under it, including
    Chinese lines opening with the comma Chinese actually uses. It also checked
    against the implementation's own list, so a gap in that list was invisible
    twice over.

    This slices at the real text column and checks an INDEPENDENT set. Only the
    wide languages are asserted, because they are the only ones this code
    wraps — the narrow ones fall through to ``textwrap`` by design, and that
    byte-identical fall-through is a guarantee of its own.
    """
    from core.i18n import set_language
    from ui.file_guide import tree_lines, tree_text_column

    forbidden = "\u3002\u3001\uff0c\uff0e\uff1a\uff1b\uff01\uff1f" \
                "\uff09\u300d\u300f\u3011\u3009\u300b\u3015\uff5d\uff3d" \
                "\u2014\u2026\uff5e" "!%),.:;?]}"
    col = tree_text_column()
    try:
        for code in ("ja", "zh_CN"):
            set_language(code)
            for line in tree_lines(62):
                if len(line) <= col:
                    continue
                text = line[col:].strip()
                assert not (text and text[0] in forbidden), (
                    f"{code}: a line opens with {text[0]!r} - {text[:30]!r}")
    finally:
        set_language("en")


def test_the_kinsoku_check_can_actually_fail():
    """Guard the guard: prove the slice reaches text, not tree art.

    The previous test passed because it never looked at a text character.
    """
    from core.i18n import set_language
    from ui.file_guide import tree_lines, tree_text_column

    col = tree_text_column()
    try:
        set_language("zh_CN")
        texts = [line[col:].strip() for line in tree_lines(62) if len(line) > col]
        real = [t for t in texts if t and t[0] not in "\u2502\u251c\u2514\u2500 "]
        assert len(real) > 20, (
            f"the text column ({col}) does not reach the explanations - only "
            f"{len(real)} real lines, so any kinsoku check here is vacuous")
    finally:
        set_language("en")

