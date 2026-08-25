"""#164 Q15 — "Location being edited: …/runs/run1/" with no project open.

The location line was never the fault: it answers as soon as a name is known,
which is exactly when it is most useful (Knut's design, #130). What put a
non-existent project on screen was the name field being pre-filled with the
factory string "ChromIQ Test Chart".

Three things had to change together, and this file holds all three:
  1. the field starts EMPTY,
  2. Generate with an empty name asks for one instead of inventing
     `Printer_Paper_Type_Instr_<timestamp>`,
  3. an existing install's stored copy of the factory name is dropped.
"""
import pathlib

import pytest


@pytest.fixture
def fresh(qapp, tmp_path):
    from core.settings import AppSettings
    from ui.main_window import MainWindow

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("session_project", "")
    s._qs.remove("chart_target_name")
    w = MainWindow(s)
    qapp.processEvents()
    yield w, tmp_path / "out"
    w.close()


def test_the_name_field_starts_empty(fresh):
    w, _ = fresh
    assert w._tab_chart._target_name_edit.text() == "", (
        "the Guided name box is pre-filled on a fresh start")
    assert w._tab_chart._manual_target_name_edit.text() == "", (
        "the Manual name box is pre-filled on a fresh start")


def test_no_location_is_shown_before_a_name_exists(fresh):
    """Basti: *"Should that line be blank until a project is open?"* — it is,
    once nothing invents a name for it to resolve."""
    w, _ = fresh
    assert w._target_ctl.location_being_edited() == ""


def test_the_location_appears_as_soon_as_you_type_one(fresh):
    """…and it must still answer BEFORE the first Generate — that is the whole
    point of the line, so blanking it unconditionally would have been wrong."""
    w, _ = fresh
    w._tab_chart._target_name_edit.setText("Canon PRO-300 Baryta")
    where = w._target_ctl.location_being_edited()
    assert "Canon" in where, f"typing a name showed no location ({where!r})"


def test_generate_with_no_name_invents_no_folder(fresh, monkeypatch):
    """`get_target_name()` is a MUTATING getter — with nothing set it makes up
    `Printer_Paper_Type_Instr_<timestamp>` and builds the chart into it."""
    from ui.tooltip_button import InfoDialog

    w, out = fresh
    shown = []
    monkeypatch.setattr(InfoDialog, "exec",
                        lambda self: shown.append(self.windowTitle()) or 0)

    before = sorted(p.name for p in out.glob("*")) if out.exists() else []
    w._tab_chart._on_generate()
    after = sorted(p.name for p in out.glob("*")) if out.exists() else []

    assert shown, "Generate said nothing about the missing name"
    assert after == before, f"Generate invented a folder: {set(after) - set(before)}"
    assert w._file_mgr.is_named() is False, (
        "Generate named the project anyway")


def test_the_ask_names_the_exact_box(fresh, monkeypatch):
    """House style: help text names the UI element you must touch."""
    from ui.tooltip_button import InfoDialog

    w, _ = fresh
    seen = {}

    def _grab(self):
        seen["title"] = self.windowTitle()
        seen["body"] = getattr(self, "_body_text", "") or self.property("body") or ""
        return 0

    monkeypatch.setattr(InfoDialog, "__init__",
                        lambda self, title, body, parent=None, **kw: (
                            seen.update(title=title, body=body), None)[1])
    monkeypatch.setattr(InfoDialog, "exec", lambda self: 0)
    monkeypatch.setattr(InfoDialog, "windowTitle", lambda self: "", raising=False)
    w._tab_chart._ask_for_a_project_name()
    assert "Printer profile project name" in seen["body"]
    assert "Generate Chart" in seen["body"]


def test_a_named_project_still_generates(fresh, monkeypatch):
    """The guard must fire ONLY when nothing is named — never on the ordinary
    path.

    Driven through the real `_on_generate`. The previous version re-implemented
    the guard's boolean in the test body and would have passed with the guard
    deleted from the source entirely.
    """
    from ui.tooltip_button import InfoDialog

    w, _ = fresh
    asked = []
    monkeypatch.setattr(InfoDialog, "exec", lambda self: asked.append(1) or 0)
    # Stop before any real Argyll work: the rename hook is the first thing
    # after the guard, so refusing there proves the guard let us through.
    reached = []
    monkeypatch.setattr(type(w._tab_chart), "_handle_target_rename",
                        lambda self, name: reached.append(name) or False)

    w._tab_chart._target_name_edit.setText("Canon PRO-300 Baryta")
    w._tab_chart._on_generate()

    assert not asked, "the guard fired even though a name was typed"
    assert reached == ["Canon PRO-300 Baryta"], (
        f"Generate did not get past the guard with a name typed ({reached})")


def test_an_open_project_is_not_asked_to_name_itself(fresh, monkeypatch):
    """Once a project IS open, an empty box is a rename question, which
    `_handle_target_rename` owns — the guard must stay out of it.

    Also driven, for the same reason as above.
    """
    from ui.tooltip_button import InfoDialog

    w, _ = fresh
    asked = []
    monkeypatch.setattr(InfoDialog, "exec", lambda self: asked.append(1) or 0)
    reached = []
    monkeypatch.setattr(type(w._tab_chart), "_handle_target_rename",
                        lambda self, name: reached.append(name) or False)

    w._file_mgr.set_target_name("Already Open")
    w._tab_chart._target_name_edit.setText("")
    w._tab_chart._on_generate()

    assert not asked, (
        "the guard fired on an open project and blocked the rename flow")
    assert reached == [""], (
        f"Generate did not reach the rename handler ({reached})")


# ----------------------------------------------------------------- migration

def test_the_factory_name_is_dropped_from_an_existing_install(tmp_path):
    from core.settings import AppSettings

    s = AppSettings()
    s._qs.setValue("chart_target_name", "ChromIQ Test Chart")
    s._qs.remove("settings_schema")
    dropped = s.migrate()
    assert any("chart_target_name" in d for d in dropped), dropped
    assert s._qs.value("chart_target_name", None) is None


def test_a_name_the_user_chose_is_left_alone(tmp_path):
    """Only the factory string goes. Anything else is the user's."""
    from core.settings import AppSettings

    s = AppSettings()
    s._qs.setValue("chart_target_name", "Canon PRO-300 Baryta")
    s._qs.remove("settings_schema")
    s.migrate()
    assert s._qs.value("chart_target_name", None) == "Canon PRO-300 Baryta"
    s._qs.remove("chart_target_name")


def test_saving_defaults_does_not_persist_a_factory_name(fresh):
    """Save-defaults deliberately does not keep the project name — it must now
    reset it to EMPTY, not to the factory string, or the field comes back
    pre-filled on the very next launch and Q15 returns.

    Driven, not read: the previous version of this test asserted on the source
    text and would have passed on a comment.
    """
    w, _ = fresh
    tc = w._tab_chart
    tc._target_name_edit.setText("A Real Project")
    tc._manual_target_name_edit.setText("A Real Project")

    tc._on_save_defaults()

    stored = w._settings.get("chart_target_name", None)
    assert not stored, (
        f"Save defaults persisted a project name ({stored!r}) — the next fresh "
        "start would come up pre-filled")

    # …and a brand-new window built on those saved defaults comes up empty.
    from ui.main_window import MainWindow
    w2 = MainWindow(w._settings)
    try:
        assert w2._tab_chart._target_name_edit.text() == "", (
            "the saved defaults still seed the name box")
    finally:
        w2.close()
