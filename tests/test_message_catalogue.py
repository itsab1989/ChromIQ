"""Every window's text is the text the model approved — checked, not claimed.

Knut, #130 beta.125: *"the message which starts with 'This run holds work made
with the chart you are about to replace' I cannot find in the Unified
Measurement Management model. Where is it? […] Only approved message text shall
be used in any of the windows. Verify that ALL message windows in the code for
the Measurement Management model conforms with the defined and reviewed Unified
Measurement Management model."*

He was right: the implementation had written its own sentences. The fix is
structural rather than a promise — the reviewed §M catalogue lives in
``workflow/measurement_messages.py``, every window renders from it, and this
file parses §M out of the design document and fails when the two disagree.

So there are three things to hold together, and a test for each link:

1. the design document's §M  ↔  ``measurement_messages.CATALOGUE``
2. ``CATALOGUE``  ↔  what the windows actually display
3. nothing displayed anywhere that is not in the catalogue
"""
from __future__ import annotations

import inspect
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_messages as M      # noqa: E402

SPEC = Path(__file__).resolve().parent.parent / "docs" / "design" / \
    "unified_measurement_management.md"


def _spec_messages() -> "dict[str, str]":
    """{ID: headline} for every message defined in §M of the document."""
    text = SPEC.read_text()
    body = text[text.index("## M. The message catalogue"):]
    body = body[:body.index("### M-x.")]
    out = {}
    for block in re.finditer(
            r"^### (M-[A-Z0-9-]+)[^\n]*\n(.*?)(?=^### |\Z)",
            body, re.M | re.S):
        mid, rest = block.group(1), block.group(2)
        headline = re.search(r"^> \*\*(.+?)\*\*\s*$", rest, re.M)
        if headline:
            out[mid] = headline.group(1).strip()
    return out


# ---- 1. the document and the catalogue agree -----------------------------
def test_the_document_defines_messages_at_all():
    spec = _spec_messages()
    assert len(spec) >= 10, f"only found {sorted(spec)}"


def test_every_message_in_the_document_exists_in_the_code():
    spec = _spec_messages()
    missing = sorted(set(spec) - set(M.CATALOGUE))
    # M-END, M-END-EMPTY, M-TI3-EMPTY and M-TI3-SHRANK belong to the measuring
    # session, which builds its text in the Measure tab; they are checked by
    # test_unified_ending.py against the same document.
    session = {"M-END", "M-END-EMPTY", "M-TI3-EMPTY", "M-TI3-SHRANK"}
    assert not (set(missing) - session), missing


def test_every_headline_is_the_documents_headline():
    """Word for word. A "corrected" headline is a changed model."""
    spec = _spec_messages()
    for mid, msg in sorted(M.CATALOGUE.items()):
        if not msg.approved:
            continue
        assert mid in spec, f"{mid} is marked approved but is not in the model"
        assert msg.title == spec[mid], (
            f"{mid}\n  code: {msg.title!r}\n  model: {spec[mid]!r}")


def test_proposed_messages_are_marked_as_such_in_the_document():
    """A message the reviewer has not seen must be visibly flagged, both in the
    code and in the document, so it cannot pass for approved."""
    text = SPEC.read_text()
    for mid in M.PROPOSED:
        # The heading that DEFINES it, not the first place it is mentioned —
        # a proposed message may well be referenced in the prose above.
        heading = f"### {mid} ·"
        assert heading in text, f"{mid} has no definition in the design document"
        block = text[text.index(heading):]
        assert "PROPOSED" in block[:300], \
            f"{mid} is defined in the document but not flagged as awaiting approval"


def test_nothing_is_quietly_proposed():
    """The proposed set is small and deliberate — if it grows, it is because
    someone added a message rather than getting one approved."""
    assert set(M.PROPOSED) == {"M-CHART-CORRUPT"}, M.PROPOSED


# ---- 2. the windows render from the catalogue ----------------------------
WINDOW_SOURCES = [
    ("ui.tabs.tab_measure", "TabMeasure", "_replace_message"),
    ("ui.tabs.tab_chart", "TabChart", "_profiling_chart_message"),
    ("ui.tabs.tab_chart", "TabChart", "_verify_chart_message"),
    ("ui.tabs.tab_chart", "TabChart", "_pages_paragraph"),
    ("ui.tabs.tab_chart", "TabChart", "_duplicate_blocked_note"),
    ("ui.tabs.tab_profile", "TabProfile", "_confirm_rebuild_over_verifications"),
]


@pytest.mark.parametrize("module,cls,method", WINDOW_SOURCES)
def test_the_window_takes_its_text_from_the_catalogue(module, cls, method):
    mod = __import__(module, fromlist=[cls])
    src = inspect.getsource(getattr(getattr(mod, cls), method))
    assert "measurement_messages" in src, \
        f"{cls}.{method} does not use the catalogue"


def _translated_literals(src: str) -> "list[str]":
    """Every literal string handed to ``tr()`` in *src*.

    Parsed rather than matched with a regular expression, so a docstring or a
    comment that happens to contain a sentence is not mistaken for one that
    reaches the screen — which is the whole distinction this test is about.
    """
    import ast
    import textwrap

    out = []
    tree = ast.parse(textwrap.dedent(src))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "tr" and node.args):
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                out.append(arg.value)
    return out


@pytest.mark.parametrize("module,cls,method", WINDOW_SOURCES)
def test_the_window_writes_no_prose_of_its_own(module, cls, method):
    """A window may translate a *reference* to the catalogue; it may not
    contain a sentence of its own. Anything long enough to be prose is one
    somebody wrote outside the reviewed model."""
    mod = __import__(module, fromlist=[cls])
    src = inspect.getsource(getattr(getattr(mod, cls), method))
    for literal in _translated_literals(src):
        assert len(literal) < 60, (
            f"{cls}.{method} shows a sentence that is not in the catalogue:\n"
            f"  {literal[:120]}…")


# ---- 3. what reaches the screen -----------------------------------------
def test_no_message_reaches_the_screen_with_a_placeholder_left():
    """Every message, rendered with its real arguments."""
    rendered = [
        M.M_REPLACE_PARTIAL.render(c=38, a=224, path="/x/y.ti3"),
        M.M_REPLACE_COMPLETE.render(a=224, path="/x/y.ti3"),
        M.M_TI3_MISMATCH.render(c=9, a=224, extra="", stem="y", path="/x"),
        M.M_REPLACE_UNCOUNTABLE.render(path="/x/y.ti3"),
        M.M_CHART_PROFILING.render(items="•  a measurement of 3 patches",
                                   folder="/x/old"),
        M.M_CHART_W4.render(c=224, v=4, folder="/x/old"),
        M.M_CHART_VERIFY.render(v=4),
        M.M_CHART_NOPAGES.render(pages="…"),
        M.M_CHART_CORRUPT.render(),
        M.M_PREVIEW_PAUSED.render(),
        M.M_PROFILE_VERIFY.render(n=4, date="2026-03-14", blocked=""),
    ]
    for title, body in rendered:
        for text in (title, body):
            assert "{" not in text and "}" not in text, text[:120]


def test_every_message_has_a_headline_and_a_body():
    for mid, msg in sorted(M.CATALOGUE.items()):
        assert msg.title and msg.body, mid
        assert not msg.title.endswith("."), \
            f"{mid}: a headline is not a sentence"


def test_no_message_uses_a_bracketed_plural():
    """House rule, and the model follows it too."""
    for mid, msg in sorted(M.CATALOGUE.items()):
        assert "(s)" not in msg.title + msg.body, mid
