"""A question with one OK button is not a question.

Knut, 2026-09-13, testing beta 8::

    Also, for Clip-border content frame, if I choose Custom text example option
    in Content input box, then a window appears saying "Replace the current
    clip-border text with the example table?", but the window has only OK
    button, so I am not given the choice to NOT replace the text.

`warning_sign.ask` took its button set from `_boxed`, which it shares with
`warn` and `inform`, and their default is a single OK. That is right for a
statement and impossible for a question. Worse than either outcome: the caller
compared the answer against `Yes`, and OK is not Yes, so the ONLY button on
screen performed the destructive branch by falling through the comparison. The
user's typed record was replaced whichever way they answered a question with
one answer.

Two halves are pinned here, because a fix to one of them alone leaves the fault
reachable: `ask` must OFFER both, and the call site must ACT on No.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_ask_offers_yes_and_no_and_defaults_to_no(qapp, monkeypatch):
    """MUTATION: drop the button default from `ask` and this goes red."""
    from PyQt6.QtWidgets import QMessageBox
    import ui.warning_sign as ws
    seen = {}

    def _spy(parent, title, text, buttons, default, set_icon):
        seen["buttons"], seen["default"] = buttons, default
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(ws, "_boxed", _spy)
    ws.ask(None, "t", "b")
    # None means "whatever `_boxed` defaults to", and `_boxed`'s default is the
    # single OK it shares with `warn` and `inform`. That IS the shipped fault,
    # so it is named here rather than left to raise a TypeError two lines down.
    assert seen["buttons"] is not None, (
        "ask() passes no button set, so it inherits _boxed's single OK: a "
        "question the user cannot decline")
    assert seen["buttons"] & QMessageBox.StandardButton.Yes, "no Yes button"
    assert seen["buttons"] & QMessageBox.StandardButton.No, (
        "the question offers no way to decline it")
    assert not (seen["buttons"] & QMessageBox.StandardButton.Ok), (
        "a question must not be answered with OK: the caller tests for Yes")
    assert seen["default"] == QMessageBox.StandardButton.No, (
        "a stray Return would destroy what the user typed")


def test_an_explicit_button_set_is_still_honoured(qapp, monkeypatch):
    """The default must not become a rule: a caller that names its own buttons
    keeps them."""
    from PyQt6.QtWidgets import QMessageBox
    import ui.warning_sign as ws
    seen = {}
    monkeypatch.setattr(ws, "_boxed",
                        lambda p, t, b, btns, d, i: seen.update(
                            buttons=btns, default=d) or QMessageBox.StandardButton.Ok)
    want = (QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard)
    ws.ask(None, "t", "b", buttons=want)
    assert seen["buttons"] == want


def test_the_real_ask_returns_no_when_no_is_clicked(qapp, monkeypatch):
    """THE WHOLE CHAIN, WITH NOTHING STUBBED OUT IN THE MIDDLE.

    An adversary round found that every test above and below stubs either
    `_boxed` or `ask`, so nothing exercised
    `ask` -> `_boxed` -> `standardButton(clickedButton())` -> `!= Yes`. It
    proved the gap by mutating `_boxed` to return an int, which is the exact
    trap `measurement_report_dialog.py` documents by name, and the whole suite
    produced no semantic failure. The shipped code is right; nothing was
    watching it.

    Only `QMessageBox.exec` is replaced here, and only to click a button
    instead of blocking, which is what a person does. Everything either side of
    it is the real thing.
    """
    from PyQt6.QtWidgets import QMessageBox
    from ui.warning_sign import ask
    clicked: dict = {}

    def _click(self):
        # The button the DEFAULT is on, which is the one a stray Return hits.
        btn = self.defaultButton() or self.button(QMessageBox.StandardButton.No)
        clicked["text"] = btn.text() if btn is not None else None
        self.setResult(0)
        # Qt reports the clicked button through `clickedButton()`, which is
        # only set by an actual click, so it is set the way a click sets it.
        self._chromiq_clicked = btn
        return 0

    monkeypatch.setattr(QMessageBox, "exec", _click, raising=False)
    monkeypatch.setattr(
        QMessageBox, "clickedButton",
        lambda self: getattr(self, "_chromiq_clicked", None), raising=False)
    answer = ask(None, "Replace?", "Replace the text?")
    assert answer == QMessageBox.StandardButton.No, (
        f"the real chain answered {answer!r}, not No; the default button was "
        f"{clicked.get('text')!r}")
    assert answer != QMessageBox.StandardButton.Yes, (
        "the caller tests for Yes, and this answer would pass that test")


# ------------------------------------------------------- the one call site
def _panel(qapp):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    return LayoutOptionsPanel()


def test_declining_keeps_the_text_the_user_typed(qapp, monkeypatch):
    """No means no: the box keeps its words and the combo goes back to Custom
    text, so the selection that asked the question does not stay showing
    "example"."""
    from PyQt6.QtWidgets import QMessageBox
    import ui.dialogs.layout_options_panel as lop
    panel = _panel(qapp)
    mine = "MY OWN RECORD, DO NOT REPLACE"
    panel.clip_text.setPlainText(mine)
    monkeypatch.setattr(lop, "ask",
                        lambda *a, **k: QMessageBox.StandardButton.No)
    panel._load_example_clip_table()
    assert panel.clip_text.toPlainText() == mine, (
        "answering No replaced the user's record anyway")
    assert panel.clip_content_mode.currentData() == "text"


def test_accepting_really_does_load_the_example(qapp, monkeypatch):
    """The control. If No and Yes did the same thing this file would pass with
    the question removed entirely."""
    from PyQt6.QtWidgets import QMessageBox
    import ui.dialogs.layout_options_panel as lop
    panel = _panel(qapp)
    panel.clip_text.setPlainText("MY OWN RECORD")
    monkeypatch.setattr(lop, "ask",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    panel._load_example_clip_table()
    got = panel.clip_text.toPlainText()
    assert got != "MY OWN RECORD" and "PRINT:" in got, got


def test_an_empty_box_is_not_asked_about(qapp, monkeypatch):
    """Nothing to lose, so nothing to confirm."""
    import ui.dialogs.layout_options_panel as lop
    panel = _panel(qapp)
    panel.clip_text.setPlainText("")
    def _never(*a, **k):
        raise AssertionError("asked about replacing an empty box")
    monkeypatch.setattr(lop, "ask", _never)
    panel._load_example_clip_table()
    assert "PRINT:" in panel.clip_text.toPlainText()
