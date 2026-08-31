"""§S4.7's window: the shape of it, not just its text.

A challenge pass mutated this window and the suite did not notice:

  * scrambling the button order to
    ["Use a different name", "Replace it", "Cancel", "Continue this project"]
    — Cancel third, the destructive answer second from the left — 98 passed;
  * `setDefaultButton(cancel)` → `(replace)`, which makes a Return keypress an
    overwrite of somebody's project — 98 passed.

The existing tests pick buttons by TEXT, so they are structurally blind to
where a button sits and which one Return will press. Both properties are
specified — §S4.7, and the code's own comments ("Cancel on the far right, not
wedged between the safe answers and the destructive one", Basti 2026-08-27;
"THE DEFAULT IS CANCEL. A Return keypress must never be an overwrite").
"""
import pathlib

import pytest


@pytest.fixture
def tab(qapp, tmp_path):
    from core.settings import AppSettings
    from ui.main_window import MainWindow

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("session_project", "")
    w = MainWindow(s)
    qapp.processEvents()
    yield w._tab_chart, tmp_path / "out"
    w.close()


def _a_project_that_holds_something(out: pathlib.Path, name: str = "taken"):
    run = out / name / "runs" / "run1"
    run.mkdir(parents=True)
    (out / name / "project.json").write_text(
        '{"schema_version": 2, "current_run": "run1", "runs": ["run1"]}')
    (run / "chart.ti3").write_text("CTI3\n")
    return out / name


def _capture_window(tab, monkeypatch):
    """Open §S4.7 and hand back the QMessageBox and the order it was given."""
    from PyQt6.QtWidgets import QMessageBox
    import ui.widgets as w

    # Patched on `ui.widgets`, not on the tab: the tab imports it INSIDE the
    # method, so it never becomes an attribute of `tab_chart`.
    seen = {}
    real_spread = w.spread_message_box_buttons

    def _spread(box, order=None, **kw):
        seen["order"] = [b.text() for b in (order or [])]
        return real_spread(box, order=order, **kw)

    monkeypatch.setattr(w, "spread_message_box_buttons", _spread)
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda self: seen.setdefault("box", self) and 0)
    tab._name_typed_by_user = True
    tab._gate_typed_project_name()
    return seen


def test_return_is_never_an_overwrite(tab, monkeypatch):
    t, out = tab
    _a_project_that_holds_something(out)
    t._manual_target_name_edit.setText("taken")

    seen = _capture_window(t, monkeypatch)

    box = seen.get("box")
    assert box is not None, "§S4.7 did not open for a project that holds work"
    default = box.defaultButton()
    assert default is not None, "no default button — Return does something unstated"
    assert default.text() == "Cancel", (
        f"Return would press {default.text()!r}. The default must be Cancel: a "
        f"keypress must never replace somebody's project.")


def test_cancel_sits_on_the_far_right_and_replace_is_not_first(tab, monkeypatch):
    t, out = tab
    _a_project_that_holds_something(out)
    t._manual_target_name_edit.setText("taken")

    seen = _capture_window(t, monkeypatch)

    order = seen.get("order")
    assert order, "the buttons were never given an explicit order"
    assert order == ["Continue this project", "Replace it",
                     "Use a different name", "Cancel"], (
        f"§S4.7's buttons are in the wrong order: {order}. Cancel belongs on "
        f"the far right, not wedged between the safe answers and the "
        f"destructive one.")


def test_the_picker_offers_a_new_run_by_default(tab, monkeypatch):
    """The only answer that cannot cost anything is a fresh run beside the work
    already there — so it is what the picker starts on."""
    t, out = tab
    root = _a_project_that_holds_something(out)
    t._manual_target_name_edit.setText("taken")

    from core.file_manager import peek_project
    picker, chosen = t._build_run_picker(peek_project(root))
    if picker is None:
        pytest.skip("no picker for this target type")
    assert chosen[0] == "", (
        f"the picker starts on run {chosen[0]!r}; it must start on a NEW run")
