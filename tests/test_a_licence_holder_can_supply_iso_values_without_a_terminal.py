"""Supplying a standard's own limit values must not need a terminal.

ChromIQ keeps the ISO 12647 tolerance values out of its own code and reads them
from a file the user supplies. Until 2026-09-20 the only way to name that file
was the environment variable `CHROMIQ_COMPLIANCE_ISO_FILE`, and the only way to
get a file of the right shape was `python scripts/iso_values_template.py`.

**Both are developer doors.** A shipped ChromIQ is a `.dmg`, a `.zip` or a
`.tar.gz` with no `scripts/` folder in it, and a variable exported in a shell
never reaches an app launched from Finder, the Dock, the Start menu or a
desktop file. So the feature existed and nobody outside this checkout could
use it. Basti, 2026-09-20: *"i just hope this is straightforward and does not
require any special knowledge"*, and *"whatever you do must work on win and
linux as well"*.

This file pins the door that answers both: a known location derived the same
way the presets folder is derived on each platform, and three buttons in the
Report limits window that write the template, install a filled-in file and
remove it again.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from core import platform_paths as pp  # noqa: E402
from workflow import compliance_sets as cs  # noqa: E402


@pytest.fixture()
def own_folder(tmp_path, monkeypatch):
    """Point the whole per-platform chain at a temp folder."""
    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "presets"))
    monkeypatch.delenv(cs.ISO_DATA_ENV, raising=False)
    cs.reset_iso_cache()
    yield tmp_path
    cs.reset_iso_cache()


def test_the_folder_is_beside_the_presets_on_every_platform(monkeypatch):
    """Not a hard-coded macOS path: the same derivation the presets use.

    `presets_dir()` already answers %APPDATA%\\ChromIQ on Windows,
    ~/Library/Preferences/ChromIQ on macOS and $XDG_CONFIG_HOME/ChromIQ on
    Linux. Deriving from it is what makes this work on all three without this
    test having to know which one it is running on.
    """
    monkeypatch.delenv("CHROMIQ_PRESETS_DIR", raising=False)
    assert pp.compliance_dir().parent == pp.presets_dir().parent
    assert pp.compliance_dir().name == "compliance"

    for plat, marker in (("win32", "ChromIQ"), ("darwin", "ChromIQ"),
                         ("linux", "ChromIQ")):
        monkeypatch.setattr(pp.sys, "platform", plat)
        assert marker in str(pp.compliance_dir()), plat


def test_a_filled_in_file_is_used_and_then_forgotten(own_folder):
    """The three buttons' whole journey, without a shell or a variable.

    #182 S-2, §23: a fresh install reads what ChromIQ SHIPS (the repository's
    file, read here, never written into this source), the user's number then
    wins its row, and "Stop using it" puts the shipped figure back. The
    precondition keeps the middle step honest: were the shipped figure the
    user's own 1.9, an install that did nothing would pass. Red on its
    mutation: make `install_user_values` or `forget_user_values` skip
    `reset_iso_cache`, and the table keeps the old figure.
    """
    from tests.helpers.iso_files import shipped_limits
    shipped = shipped_limits("iso_12647_7")["all_de00_avg"]
    assert shipped.number != pytest.approx(1.9)
    assert cs.iso_data_path_text() == "", "a fresh install starts with none"
    assert cs.factory_limits("iso_12647_7")["all_de00_avg"] == shipped

    # 1. the template, as the first button writes it
    filled = own_folder / "mine.json"
    doc = json.loads(cs.iso_values_template())
    doc["iso_12647_7"]["all_de00_avg"] = 1.9
    filled.write_text(json.dumps(doc), encoding="utf-8")

    # 2. the second button
    where = cs.install_user_values(filled)
    assert where == cs.user_values_path()
    assert where.is_file(), "the file was not copied into ChromIQ's own folder"
    assert cs.iso_data_path_text() == str(where)
    lim = cs.factory_limits("iso_12647_7")["all_de00_avg"]
    assert lim.kind == "value" and lim.number == pytest.approx(1.9)

    # it is COPIED, so tidying up the source does not take the values away
    filled.unlink()
    cs.reset_iso_cache()
    assert cs.factory_limits("iso_12647_7")["all_de00_avg"].number == \
        pytest.approx(1.9)

    # 3. the third button
    assert cs.forget_user_values() is True
    assert cs.iso_data_path_text() == ""
    assert cs.factory_limits("iso_12647_7")["all_de00_avg"] == shipped
    assert cs.forget_user_values() is False, "removing nothing is not an event"


def test_rubbish_is_refused_before_it_is_installed(own_folder):
    """A hand-edited file with a trailing comma must not become the live one."""
    bad = own_folder / "bad.json"
    bad.write_text('{"iso_12647_7": {"all_de00_avg": 1.9,}}', encoding="utf-8")
    with pytest.raises(ValueError):
        cs.install_user_values(bad)
    assert not cs.user_values_path().is_file()
    assert cs.iso_data_path_text() == ""


def test_the_environment_variable_still_wins(own_folder, monkeypatch):
    """The developer door stays open: the suite and this checkout use it."""
    doc = json.loads(cs.iso_values_template())
    doc["iso_12647_7"]["all_de00_avg"] = 1.1
    own = own_folder / "own.json"
    own.write_text(json.dumps(doc), encoding="utf-8")
    cs.install_user_values(own)

    doc["iso_12647_7"]["all_de00_avg"] = 2.2
    env = own_folder / "env.json"
    env.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setenv(cs.ISO_DATA_ENV, str(env))
    cs.reset_iso_cache()
    assert cs.factory_limits("iso_12647_7")["all_de00_avg"].number == \
        pytest.approx(2.2)
    cs.forget_user_values()


@pytest.fixture()
def qapp_or_skip():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_pressing_each_button_really_runs(qapp_or_skip, tmp_path, monkeypatch):
    """PRESS THE BUTTONS. The first version of this file read the slots'
    SOURCE with `inspect.getsource` and asserted the right names appeared in
    it, and it passed while all three buttons did nothing at all: `Path` was
    never imported, every slot raised `NameError`, and Qt swallows an exception
    raised inside a slot. Basti found it in the shipped beta 26 within minutes.

    That is this project's oldest shape, a guard that tests the HELPER instead
    of the DOOR, and reading source text is the purest form of it.

    The three buttons now live in `ReferenceValuesDialog`, one section per
    source, because Basti saw that one data source costing three buttons meant
    two would cost six. This presses them where they are.
    """
    import ui.widgets as W
    from ui.dialogs.reference_values_dialog import ReferenceValuesDialog

    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "presets"))
    monkeypatch.delenv(cs.ISO_DATA_ENV, raising=False)
    cs.reset_iso_cache()

    template = tmp_path / "template.json"
    asked: dict = {}
    monkeypatch.setattr(W, "save_file_dialog",
                        lambda *a, **k: (asked.update(save=k), str(template))[1])
    monkeypatch.setattr(W, "open_file_dialog",
                        lambda *a, **k: (asked.update(open=k), str(template))[1])

    dlg = ReferenceValuesDialog()
    said: list = []
    dlg._say = said.append

    def iso_row():
        """The ISO row AS IT IS NOW. The rows are rebuilt when what a source
        supplies changes, so a widget captured before a press is a widget that
        may no longer be in the window; holding one and asserting on it is how
        a guard ends up measuring something nobody can see."""
        dlg._refresh()
        return next((r for r in dlg._rows if r[0].key == "iso12647"), None)

    try:
        src, key, state, forget = iso_row()
        assert key == "iso12647"
        assert not forget.isEnabled(), "nothing is supplied, so nothing to forget"
        assert forget.isVisible() or not dlg.isVisible(), \
            "the one-item source must still SHOW its Stop button"
        assert "Nothing supplied" in state.text()

        dlg._template(src)
        assert template.is_file(), "the first button wrote nothing"
        assert json.loads(template.read_text(encoding="utf-8"))["iso_12647_7"]

        dlg._install(src)
        assert cs.user_values_path().is_file(), "the second button installed nothing"
        _s, _k, state, forget = iso_row()
        assert forget.isEnabled()
        assert "In use:" in state.text(), "the window does not say what is in use"

        dlg._forget(src, "iso12647")
        assert not cs.user_values_path().is_file(), "the third button removed nothing"
        _s, _k, state, forget = iso_row()
        assert not forget.isEnabled()
        assert len(said) == 3, said
    finally:
        dlg.close()
        cs.reset_iso_cache()


def test_the_report_limits_window_has_one_door_and_it_is_small(qapp_or_skip,
                                                               tmp_path):
    """Basti, twice on the shipped beta: *"the three buttons should be reduced
    in heigth"*, then *"the current ones are still big ... they could be
    smaller i think"*, and then the reason it matters: *"if you are putting in
    3 more buttons there will be quite a lot in the end"*.

    So the Report limits window carries ONE button, at 18 px, which is that
    window's own smallest interactive control, its check boxes. The three
    actions moved behind it. This guard fails the day a second one appears
    beside it, which is the failure he predicted.
    """
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QPushButton
    from core.settings import AppSettings
    from ui.dialogs.thresholds_dialog import ThresholdsDialog

    s_ = AppSettings()
    s_._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    dlg = ThresholdsDialog(s_)
    try:
        # 26, AND THE 18 THIS ONCE ASSERTED WAS NEVER ON SCREEN. The door was
        # built with `setFixedHeight(18)`, which this read back happily from a
        # dialog that was never shown -- while the app's own stylesheet
        # (`QPushButton { padding: 6px 18px; min-height: 28px; }`) made it
        # 42 px in the window, which is what Basti was looking at when he asked
        # a SECOND time for it to be smaller. Round 30 measured it and it is a
        # per-widget stylesheet now, the same one the window's own "Restore
        # this column" button has always used: 26 px, laid out, everywhere.
        # `tests/test_a_short_button_is_short_on_screen.py` is the guard that
        # can see this, because it shows the dialog first; this line only has
        # to stop being a lie.
        assert dlg._iso_values_btn.height() == 26, dlg._iso_values_btn.height()
        # and it is alone: no leftover sibling from the three-button version
        for name in ("_iso_template_btn", "_iso_use_btn", "_iso_forget_btn"):
            assert not hasattr(dlg, name), f"{name} is still in this window"
        # the grey line says which numbers are in force without a click
        assert dlg._iso_state_lbl.text(), "the window does not say what is in use"
    finally:
        dlg.close()


def test_a_second_source_costs_no_button_in_the_report_limits_window(
        qapp_or_skip, tmp_path):
    """The whole point of the one door, now that the second source is real.

    Fogra's reference data joined `sources()` on 2026-09-20, and this asks the
    two questions that matter about that: the Report limits window still has
    exactly ONE button for all of it, and the window behind the door really
    grew a section rather than merely gaining a list entry.

    IT OPENS BOTH WINDOWS. The version this replaced read the SOURCE of
    `sources()` and of `__init__` with `inspect.getsource` and asserted two
    substrings appeared in them, which is the shape that let beta 26 ship three
    buttons that raised `NameError` on every press. A guard that reads code
    cannot fail when the code is right and the window is wrong.

    MUTATION, run before this sentence was written: drop `fogra_source()` from
    `sources()` and the section count goes 2 -> 1 and this goes red; add a
    second button to the Report limits window and the door count goes 1 -> 2
    and this goes red.
    """
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QFrame, QPushButton
    from core.settings import AppSettings
    from ui.dialogs.reference_values_dialog import (ReferenceValuesDialog,
                                                    sources)
    from ui.dialogs.thresholds_dialog import ThresholdsDialog

    keys = [s.key for s in sources()]
    assert keys == ["iso12647", "fogra"], keys

    s_ = AppSettings()
    s_._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    th = ThresholdsDialog(s_)
    try:
        doors = [b for b in th.findChildren(QPushButton)
                 if "reference" in (b.text() or "").lower()
                 or "referenz" in (b.text() or "").lower()]
        assert len(doors) == 1, [b.text() for b in doors]
    finally:
        th.close()

    dlg = ReferenceValuesDialog()
    try:
        sections = [f for f in dlg.findChildren(QFrame)
                    if f.frameShape() == QFrame.Shape.StyledPanel]
        assert len(sections) == len(keys) == 2, len(sections)
        assert set(dlg._item_boxes) == {"iso12647", "fogra"}
        # and Fogra's section says something about EVERY set, not one line
        fogra_rows = [r for r in dlg._rows if r[0].key == "fogra"]
        assert len(fogra_rows) >= 11, len(fogra_rows)
    finally:
        dlg.close()


def test_the_window_behind_the_door_explains_itself(qapp_or_skip, tmp_path,
                                                    monkeypatch):
    """What the dropped icon guard was really protecting, kept.

    The three hover tooltips and the one ⓘ in the Report limits window are
    gone with the three buttons. The explanation moved into the window behind
    the door, and the two sentences that exist purely to reassure a reader must
    survive any future edit of it: what ChromIQ's own numbers are (or WHY it
    has none), and that what you supply never leaves the computer.

    #182 S-2, §23 item 4: the first sentence asks what ships. The repository's
    file ships both sets, so it says so and says a supplied value takes the
    shipped one's place; over an empty shipped file, made by fixture, it says
    WHY the numbers are absent. Red on its mutation: hard-code either sentence
    and the other state fails.
    """
    from tests.helpers.iso_files import use_empty_shipped_iso, use_repo_iso
    from ui.dialogs.reference_values_dialog import ReferenceValuesDialog, iso_source

    use_repo_iso(monkeypatch)
    src = iso_source()
    assert "ships the published values of both ISO columns" in src.why, src.why
    assert "takes the place of ChromIQ's" in src.why, src.why
    assert "paid standard" not in src.why, "it still says nothing ships"
    use_empty_shipped_iso(tmp_path, monkeypatch)
    empty = iso_source()
    cs.reset_iso_cache()
    assert "paid standard" in empty.why, "it does not say WHY the numbers are absent"
    assert "—" not in empty.why, "em dash"
    help_text = ReferenceValuesDialog._help(src)
    for must in ("Save a file to fill in", "Use a file I filled in",
                 "Stop using it"):
        assert must in help_text, f"the ⓘ does not mention {must!r}"
    assert "does not send them anywhere" in help_text, \
        "it does not say the values stay on this computer"
    assert "—" not in help_text and "—" not in src.why, "em dash"


# ---------------------------------------------------------------------------
# Challenge round 31
# ---------------------------------------------------------------------------
def _a_fogra_file(descriptor: str, fields: str, rows: "list[str]") -> bytes:
    """A CGATS file with Fogra's own shape, CRLF and all. See
    `tests/test_a_newer_fogra_file_can_arrive_without_a_new_chromiq.py` for
    why LF here would make every guard pass over a reader that refuses every
    real file."""
    body = ["ISO28178", f'FILE_DESCRIPTOR\t"{descriptor}"',
            'ORIGINATOR\t"Fogra, www.fogra.org"', 'CREATED\t"31-Jul-2024"',
            f"NUMBER_OF_FIELDS\t{len(fields.split())}", "BEGIN_DATA_FORMAT",
            fields, "END_DATA_FORMAT", f"NUMBER_OF_SETS\t{len(rows)}",
            "BEGIN_DATA", *rows, "END_DATA", ""]
    return "\r\n".join(body).encode("utf-8")


def test_stopping_a_set_chromiq_ships_nothing_for_does_not_claim_one(
        qapp_or_skip, tmp_path, monkeypatch):
    """**THE SENTENCE WAS UNTRUE ABOUT THE ONE SET THAT PROVES THE DESIGN.**

    FOGRA61 is still beta in Fogra's archive, ChromIQ ships nothing for it, and
    the commit that built this calls it "the case that proves it is an upgrade
    path and not an override". Press "Stop using it" on it and the window said
    *"ChromIQ is back to the copy of FOGRA61 that shipped with it"*. Measured
    challenge round 31: at that moment `by_id("FOGRA61")` is None and the row
    the user just pressed is gone from the window behind the message.

    This presses the REAL Stop button on the REAL row, for both kinds of set,
    and reads the sentence the window produced.

    MUTATION, run: make `fogra_source().forgotten` return the shipped-copy
    sentence unconditionally and this goes red on the FOGRA61 half while the
    FOGRA51 half stays green.
    """
    from ui.dialogs.reference_values_dialog import ReferenceValuesDialog
    from workflow import reference_sets as rs

    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "presets"))
    rs.reset_cache()
    assert str(tmp_path) in str(rs.user_dir()), rs.user_dir()

    ships = tmp_path / "FOGRA51_new.txt"
    ships.write_bytes(_a_fogra_file(
        "FOGRA51_MW3_Subset",
        "SAMPLE_ID\tCMYK_C\tCMYK_M\tCMYK_Y\tCMYK_K\tLAB_L\tLAB_A\tLAB_B",
        ["1\t0\t0\t0\t0\t95.10\t1.40\t-6.10"]))
    ships_not = tmp_path / "FOGRA61_beta.txt"
    ships_not.write_bytes(_a_fogra_file(
        "3D-DesignRGB_FOGRA61(beta)",
        "SAMPLE_ID\tRGB_R\tRGB_G\tRGB_B\tLAB_L\tLAB_A\tLAB_B",
        ["1\t0\t0\t0\t11\t0\t0", "2\t255\t255\t255\t91\t-1\t4"]))
    rs.install_user_file(ships)
    rs.install_user_file(ships_not)

    dlg = ReferenceValuesDialog()
    # SHOWN, BECAUSE `isVisible()` ON A CHILD OF A HIDDEN DIALOG IS FALSE AND
    # A "the button is not there" FAILURE WOULD THEN BE THE GUARD'S OWN. The
    # button's visibility is the thing under test here: `always_show_forget` is
    # False for Fogra, so the Stop button appears only on the rows it can act
    # on, and a guard that could not see it would prove the opposite.
    dlg.show()
    qapp_or_skip.processEvents()
    said: list = []
    dlg._say = said.append

    def row(set_id):
        """The row AS IT IS NOW: `_fill_items` destroys and rebuilds them, so a
        widget held across a press is one nobody can see any more."""
        dlg._refresh()
        return next((r for r in dlg._rows
                     if r[0].key == "fogra" and r[1] == set_id), None)

    try:
        r61 = row("FOGRA61")
        assert r61 is not None, "the set the user supplied is not in the window"
        assert r61[3].isVisible() and r61[3].isEnabled(), \
            "there is nothing for the user to press"
        r61[3].click()
        assert len(said) == 1, said
        assert "ships no copy of that set" in said[0], said[0]
        assert "shipped with it" not in said[0], \
            "it still claims a copy that does not exist"
        assert "—" not in said[0]
        assert rs.by_id("FOGRA61") is None, "the fixture did not actually stop"
        assert row("FOGRA61") is None, "the row is still in the window"

        # ...and the set that DOES ship still gets the sentence it always had
        r51 = row("FOGRA51")
        assert r51 is not None and r51[3].isEnabled()
        r51[3].click()
        assert len(said) == 2, said
        assert "back to the copy of FOGRA51 that shipped with it" in said[1]
        assert rs.by_id("FOGRA51") is not None, "a shipped set must come back"
        assert not rs.by_id("FOGRA51").supplied_by_user
    finally:
        dlg.close()
        rs.reset_cache()


def test_the_window_shows_the_line_the_module_builds(qapp_or_skip, tmp_path,
                                                     monkeypatch):
    """`in_force_lines()` built these sentences and NOTHING ON SCREEN CALLED
    IT: the window built the same three sentences again, inline. A guard on the
    function therefore proved nothing about the window, which is this project's
    own recorded way for a guard to lie.

    So this reads the text off the labels the window actually puts in its
    layout and requires it to be, character for character, what the module
    says. One implementation, one guard.

    MUTATION, run: go back to building the sentence inside `items()` (or change
    one word of either copy) and this goes red.
    """
    from ui.dialogs.reference_values_dialog import ReferenceValuesDialog
    from workflow import reference_sets as rs

    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "presets"))
    rs.reset_cache()
    mine = tmp_path / "FOGRA61_beta.txt"
    mine.write_bytes(_a_fogra_file(
        "3D-DesignRGB_FOGRA61(beta)",
        "SAMPLE_ID\tRGB_R\tRGB_G\tRGB_B\tLAB_L\tLAB_A\tLAB_B",
        ["1\t0\t0\t0\t11\t0\t0", "2\t255\t255\t255\t91\t-1\t4"]))
    rs.install_user_file(mine)

    from PyQt6.QtWidgets import QLabel
    dlg = ReferenceValuesDialog()
    dlg.show()
    qapp_or_skip.processEvents()
    try:
        dlg._refresh()
        on_screen = [lbl.text() for s, _k, lbl, _b in dlg._rows
                     if s.key == "fogra"]
        assert on_screen == rs.in_force_lines(), \
            "the window and the module disagree about what is in force"
        assert len(on_screen) == 12, on_screen

        # AND THE SECOND LINE, WHICH IS A WHOLE SEPARATE LABEL: it is not in
        # `_rows` (nothing acts on it), so reading `_rows` alone would have
        # proved the window shows the one thing this round added and missed
        # whether it shows the other.
        every = [lb.text() for lb in dlg.findChildren(QLabel)
                 if (lb.text() or "").strip()]
        says = rs.what_the_file_says(rs.by_id("FOGRA61"))
        assert says and "3D-DesignRGB_FOGRA61(beta)" in says, says
        assert "31-Jul-2024" in says, (
            "the window says when the user acted and not which file it is")
        assert says in every, (
            "the module builds the file's own line and the window drops it")
        # ...and it is NOT folded into the first line, which is what made it
        # wrap across the row beneath it. Measured on screen, round 31.
        assert all(says not in t for t in on_screen), on_screen
        for text in on_screen + [says]:
            assert "—" not in text, text
    finally:
        dlg.close()
        rs.reset_cache()
