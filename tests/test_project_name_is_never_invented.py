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


def _stub_name_prompt(monkeypatch, answer):
    """Stand in for the name dialog, recording that it was opened.

    Patched on the module, because `_ask_for_a_project_name` imports the
    function inside the method. *answer* is the name a person would type, or
    None for Cancel.
    """
    import ui.dialogs.name_prompt as np
    calls = []

    def _fake(parent, *, prefill="", body=None, **kw):
        calls.append(prefill)
        return answer

    monkeypatch.setattr(np, "ask_for_project_name", _fake)
    return calls


def test_generate_with_no_name_invents_no_folder(fresh, monkeypatch):
    """`get_target_name()` is a MUTATING getter — with nothing set it makes up
    `Printer_Paper_Type_Instr_<timestamp>` and builds the chart into it."""
    w, out = fresh
    asked = _stub_name_prompt(monkeypatch, None)      # the person cancels

    before = sorted(p.name for p in out.glob("*")) if out.exists() else []
    w._tab_chart._on_generate()
    after = sorted(p.name for p in out.glob("*")) if out.exists() else []

    assert asked, "Generate said nothing about the missing name"
    assert after == before, f"Generate invented a folder: {set(after) - set(before)}"
    assert w._file_mgr.is_named() is False, (
        "Generate named the project anyway")


def test_the_ask_takes_the_name_instead_of_sending_you_away(fresh, monkeypatch):
    """The dialog answers its own question (Basti, 2026-08-30).

    It used to explain that the name box was empty, name the box, and tell the
    person to type there and repeat what they had just done. Now it takes the
    name, writes it into the field, and reports that the caller may go on.
    """
    w, _ = fresh
    tab = w._tab_chart
    _stub_name_prompt(monkeypatch, "Canon PRO-300 Baryta Gloss")

    assert tab._ask_for_a_project_name() is True
    assert tab._active_name_field().text() == "Canon PRO-300 Baryta Gloss"
    # AND §S4.7 MUST SPEAK FOR IT. `setText` never fires `textEdited`, so
    # without an explicit flag a name that collides is accepted in silence.
    assert tab._name_typed_by_user is True


def test_cancelling_the_ask_leaves_the_name_alone(fresh, monkeypatch):
    """Cancel must change nothing at all (#175)."""
    w, _ = fresh
    tab = w._tab_chart
    _stub_name_prompt(monkeypatch, None)

    assert tab._ask_for_a_project_name() is False
    assert tab._active_name_field().text() == ""
    # `getattr` with a default, the way the tab itself reads this flag: it is
    # only created once something sets it.
    assert getattr(tab, "_name_typed_by_user", False) is False


def test_the_name_dialog_refuses_what_a_folder_cannot_hold(qapp):
    """Shape-only validation: the dialog never asks about collisions — §S4.7
    owns that question and owns it alone."""
    from ui.dialogs.name_prompt import validate

    assert validate("Canon PRO-300 Baryta Gloss") is None
    assert validate("") is not None
    assert validate("   ") is not None
    assert validate("a/b") is not None            # a folder cannot hold it
    assert validate("///") is not None            # sanitises away to nothing
    assert validate("...") is not None
    assert validate("2026") is None               # digits alone are a real name


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


def test_a_name_given_in_the_dialog_is_checked_against_existing_projects(
        fresh, monkeypatch):
    """§S4.7 MUST SEE THE NAME THE DIALOG RETURNED.

    The regression this pins was silent and destructive. §S4.7 compares the name
    in the box with the projects on disk; asked while the box was still empty it
    had nothing to compare, waved the build through, and the name supplied by
    the dialog afterwards was never checked against anything. Driven against the
    shipped build: the same name typed into the BOX produced the four-button
    "there is already a project called…" window, while typed into the DIALOG it
    replaced seven files — including the .ti2 a printed sheet is read against —
    with no window at all.

    So the order is the invariant: ask first, gate second.
    """
    w, _out = fresh
    tab = w._tab_chart
    _stub_name_prompt(monkeypatch, "ZZ-already-there")

    seen = []

    def _gate(*_a, **_k):
        field = tab._active_name_field()
        seen.append(field.text().strip() if field is not None else "")
        return False, False          # refuse, so nothing is built either way

    monkeypatch.setattr(type(tab), "_gate_typed_project_name", _gate)

    tab._manual_target_name_edit.setText("")
    tab._on_generate()

    assert seen, "§S4.7 was never asked at all"
    assert seen[0] == "ZZ-already-there", (
        "§S4.7 was asked about {!r} — it must be asked about the name the "
        "person actually gave, or a collision goes unreported".format(seen[0]))


def test_a_prebuilt_preset_asks_before_it_gates(fresh, monkeypatch):
    """The prebuilt route settles the name BEFORE §S4.7, or not at all.

    `_apply_prebuilt_preset` gates and then hands `gate_already_asked=True` down
    to `_create_prebuilt_target`, so a guard inside the latter can never get in
    front of the question. Without the ask up here, §S4.7 was asked while the
    name box was still empty — nothing to compare — and the name given
    afterwards overwrote a project of the same name with no window at all.

    Written because a verification pass proved the guard had no test: deleting
    it left 333 targeted tests green while the fault came straight back on
    screen.
    """
    from ui.tabs.tab_chart import ABW1110_PRESET_KEY

    w, _out = fresh
    tab = w._tab_chart
    _stub_name_prompt(monkeypatch, "ZZ-prebuilt-name")

    seen = []

    def _gate(*_a, **_k):
        f = tab._manual_target_name_edit
        seen.append(f.text().strip() if f is not None else "")
        return False, False          # refuse, so nothing is built either way

    monkeypatch.setattr(type(tab), "_gate_route_and_replace", _gate)
    monkeypatch.setattr(type(tab), "_revert_preset_combo",
                        lambda self, *a, **k: None, raising=False)

    tab._manual_target_name_edit.setText("")
    tab._apply_prebuilt_preset(ABW1110_PRESET_KEY)

    assert seen, "§S4.7 was never asked on the prebuilt route"
    assert seen[0] == "ZZ-prebuilt-name", (
        "§S4.7 was asked about {!r} — on this route the name must be settled "
        "before the gate, because the gate is never asked again".format(seen[0]))


def test_the_already_exists_line_goes_when_the_name_does(fresh):
    """Basti, 2026-08-31, driven on screen: pick a preset, type a name that
    already exists, get the warning, cancel — and the line stayed on screen
    over an EMPTY name box, describing a name that was no longer there.

    Backing out restores the name at step 8 of `_restore_preset_state` with the
    field's signals BLOCKED, and the line is wired to `textChanged`, so it never
    heard. Anything that puts the name back silently has to say so.
    """
    w, out = fresh
    (out / "test").mkdir(parents=True, exist_ok=True)
    (out / "test" / "project.json").write_text('{"schema_version": 2, "runs": []}')

    tab = w._tab_chart
    field = tab._manual_target_name_edit
    lbl = tab._manual_project_exists_lbl

    field.setText("test")
    tab._refresh_project_exists_line()
    assert not lbl.isHidden(), "the line never appeared for an existing project"

    # Exactly what the undo does: put the old name back without a peep.
    field.blockSignals(True)
    field.setText("")
    field.blockSignals(False)
    assert not lbl.isHidden(), "precondition: the line is still up (the bug)"

    tab._refresh_project_exists_line()
    assert lbl.isHidden(), (
        "the line outlived the name it described — it sat over an empty box")


# ---------------------------------------------------------------------------
# Guards that a verification pass proved DELETABLE with the suite still green.
# Each of these drives the real method, not a helper beside it; each was
# mutation-tested by deleting the line it guards.
# ---------------------------------------------------------------------------

def test_an_unusable_name_typed_in_the_box_stops_the_build(fresh, monkeypatch):
    """`///` in the name box must reach the dialog, not the filesystem.

    It passes a check for forbidden characters and then sanitises away to
    nothing, at which point `FileManager._sanitise` substitutes "session" — so
    the build landed in a folder of that name with no window at all. The guard
    is one `validate` call inside `_name_needs_asking`; deleting it re-opened
    this on all four routes at once while the everyday tier stayed green.
    """
    w, out = fresh
    tab = w._tab_chart
    asked = _stub_name_prompt(monkeypatch, None)         # the person cancels
    built = []
    monkeypatch.setattr(tab._creator, "load_ti1_and_generate_preview",
                        lambda *a, **k: built.append(a), raising=False)

    tab._manual_target_name_edit.setText("///")
    tab._on_generate()

    assert asked, "an unusable name went through without a word"
    assert not built, "a chart was built from a name that makes no folder"
    assert not (out / "session").exists(), "the sanitiser's fallback was used"
    assert w._file_mgr.is_named() is False


def test_backing_out_of_a_preset_takes_the_collision_line_with_it(fresh):
    """Drives `_restore_preset_state` itself.

    The earlier test for this called `_refresh_project_exists_line()` by hand
    and so proved only that the refresh works — never that the undo calls it,
    which is the whole bug. This takes a real snapshot and restores it.
    """
    w, out = fresh
    (out / "test").mkdir(parents=True, exist_ok=True)
    (out / "test" / "project.json").write_text('{"schema_version": 2, "runs": []}')
    tab = w._tab_chart
    lbl = tab._manual_project_exists_lbl

    snap = tab._snapshot_preset_state()
    assert snap is not None, "no snapshot — this test would prove nothing"

    tab._manual_target_name_edit.setText("test")
    tab._refresh_project_exists_line()
    assert not lbl.isHidden(), "precondition: the line is up for 'test'"

    tab._restore_preset_state(snap)

    assert tab._manual_target_name_edit.text().strip() != "test", (
        "precondition: the undo did not put the old name back")
    assert lbl.isHidden(), (
        "the line outlived the name — `_restore_preset_state` restores the "
        "field with signals blocked, so it must refresh the line itself")


def test_the_dialog_is_told_how_to_recognise_an_existing_project(fresh,
                                                                 monkeypatch):
    """The notice is only as real as the callback behind it."""
    w, out = fresh
    (out / "test").mkdir(parents=True, exist_ok=True)
    (out / "test" / "project.json").write_text('{"schema_version": 2, "runs": []}')
    tab = w._tab_chart

    import ui.dialogs.name_prompt as np
    seen = {}

    def _fake(parent, *, prefill="", body=None, exists=None, **kw):
        seen["exists"] = exists
        return "ZZ-answer"

    monkeypatch.setattr(np, "ask_for_project_name", _fake)
    tab._ask_for_a_project_name()

    check = seen.get("exists")
    assert callable(check), "the dialog was given no way to spot a collision"
    assert check("test") is True, "a real project was not recognised"
    assert check("ZZ-not-a-project") is False
    assert check("") is False
