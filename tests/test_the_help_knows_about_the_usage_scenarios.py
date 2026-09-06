"""The scanner and camera help teaches the usage scenarios, and keeps teaching
them.

**What went wrong, and why nothing caught it.** The three usage scenarios
landed on 2026-09-06 (``97da3224f`` / ``af2d429234``). Neither commit opened
``ui/dialogs/welcome_dialog.py``, and the window's own ⓘ had not been touched
since 2026-07-13. So on the day the feature shipped:

* both printable help cards still taught the manual route the scenarios
  replace, step by step, three controls at a time;
* the window's ⓘ told the reader to *"choose one at the top of the window"*
  when the top of the window had become the scenario radios, and to *"click
  Build profile with scanner or camera"* when that button reads **"Build
  printer profile"** in printer mode;
* ``grep "usage scenario" tests/`` returned nothing at all.

That last line is the fault this file exists for. A card can only go stale
silently if nothing reads it, so every check here is anchored on something the
WINDOW says — the scenario labels come off the live radio buttons, the
settings off ``scanner_colprof`` — and never on a sentence copied into a test.

**Knut, 2026-09-06**, who set the shape as well as the subject:

    *"A user should be guided with simple steps, and given the more detailed
    explanations as notes for a deeper understanding, if the user decides to
    want that."*

So there are two things to hold, and both are checked below: the cards must
NAME the scenarios, and the long explanations must be NOTES rather than
numbered steps.
"""
from __future__ import annotations

import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QPushButton, QRadioButton  # noqa: E402

from core.settings import DEFAULTS                                   # noqa: E402

#: The two cards this is about.
SCANNER_CARDS = ("scanner_profile", "printer_from_scan")


class _FakeSettings:
    def __init__(self, **overrides):
        self._store = {**DEFAULTS, **overrides}
        if not self._store.get("custom_output_path"):
            self._store["custom_output_path"] = tempfile.mkdtemp(
                prefix="chromiq-cr-")

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, value):
        self._store[key] = value


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def dlg(_app, tmp_path_factory):
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    d = ScannerProfileDialog(object(), _FakeSettings(
        custom_output_path=str(tmp_path_factory.mktemp("cr-scenarios"))))
    yield d
    d.deleteLater()


def _cards():
    from ui.dialogs.welcome_dialog import WORKFLOWS
    return list(WORKFLOWS)


def _card(key):
    return next(c for c in _cards() if c.get("key") == key)


def _notes_of(step):
    return tuple(step[3]) if len(step) > 3 else ()


def _steps_text(key) -> str:
    return " ".join(str(s[1]) for s in _card(key)["steps"])


def _card_text(key) -> str:
    """Steps and notes together — everything the printed sheet carries."""
    parts = []
    for step in _card(key)["steps"]:
        parts.append(str(step[1]))
        for heading, body in _notes_of(step):
            parts += [str(heading), str(body)]
    return " ".join(parts)


def _scenario_labels(d) -> "dict[str, str]":
    """{scenario key: the label on its radio button}, READ OFF THE WINDOW.

    Not copied here. A label reworded in the window has to reach the help, and
    the only way a test can insist on that is to ask the window."""
    return {key: rb.text() for key, rb in d._scenario_radios.items()}


# --------------------------------------------------- the window still has them
def test_the_window_really_offers_three_usage_scenarios(dlg):
    """The premise of every check below. If the feature is renamed or removed,
    this fails first and says so, instead of the rest failing obscurely."""
    from ui.dialogs import scanner_colprof as sc

    labels = _scenario_labels(dlg)
    assert set(labels) == set(sc.SCENARIOS), sorted(labels)
    assert all(labels.values()), "a scenario radio has no label"
    radios = [rb for rb in dlg.findChildren(QRadioButton)
              if rb in dlg._scenario_radios.values()]
    assert len(radios) == 3


# ------------------------------------------------------------ the help cards
@pytest.mark.parametrize("key", SCANNER_CARDS)
def test_the_card_names_the_usage_scenario_feature(key):
    """A card that never says the words cannot send anybody to the control."""
    blob = _card_text(key).lower()
    assert "usage scenario" in blob or "scenario" in blob, (
        f"{key} does not mention the usage scenarios at all")


def test_the_scanner_card_names_the_everyday_and_the_instrument_scenario(dlg):
    labels = _scenario_labels(dlg)
    from ui.dialogs import scanner_colprof as sc

    blob = _card_text("scanner_profile")
    for which in (sc.SCENARIO_EVERYDAY, sc.SCENARIO_INSTRUMENT):
        assert labels[which] in blob, (
            "the scanner card does not quote the scenario the user has to "
            f"pick: {labels[which]!r}")


def test_the_printer_card_names_the_instrument_and_the_printer_scenario(dlg):
    labels = _scenario_labels(dlg)
    from ui.dialogs import scanner_colprof as sc

    blob = _card_text("printer_from_scan")
    for which in (sc.SCENARIO_INSTRUMENT, sc.SCENARIO_PRINTER):
        assert labels[which] in blob, (
            "the printer card does not quote the scenario the user has to "
            f"pick: {labels[which]!r}")


def test_a_card_that_lists_the_three_settings_must_also_name_the_scenario():
    """The check that would have caught the whole thing.

    ``SETUP_INSTRUMENT`` is the feature that sets three controls from one radio
    button. Any card still spelling those three out is describing the manual
    route, and if it does that without naming the scenario, it is teaching the
    long way round as though the short one did not exist. That is precisely
    what both cards did on the day the scenarios shipped.
    """
    from ui.dialogs import scanner_colprof as sc

    wanted = [dict(sc.PTYPE_CHOICES)[sc.SETUP_INSTRUMENT["ptype"]],
              dict(sc.QUALITY_CHOICES)[sc.SETUP_INSTRUMENT["quality"]],
              dict(sc.WP_MODE_CHOICES)[sc.SETUP_INSTRUMENT["wp_mode"]]]
    for card in _cards():
        if not card.get("steps"):
            continue
        blob = _card_text(card["key"])
        if not all(w in blob for w in wanted):
            continue
        assert "scenario" in blob.lower(), (
            f"{card['key']} spells out all three measuring settings but never "
            "names the usage scenario that sets them")


def test_that_rule_really_fires_on_the_cards_it_was_written_for():
    """Guard the guard, on the REAL text it was written against.

    The check above is a low bar by design, and a low bar is exactly the kind
    that quietly stops testing anything. So it is run here against the two
    cards AS THEY SHIPPED IN 4.1.5-beta.11, whose text is kept in
    `tests/data/`: both spell all three settings out and neither contains the
    word "scenario" anywhere. If this stops failing, the rule above has stopped
    meaning anything.
    """
    import json
    from pathlib import Path

    from ui.dialogs import scanner_colprof as sc

    before = json.loads(
        (Path(__file__).parent / "data" / "help_cards_before_b8_93.json")
        .read_text(encoding="utf-8"))
    wanted = [dict(sc.PTYPE_CHOICES)[sc.SETUP_INSTRUMENT["ptype"]],
              dict(sc.QUALITY_CHOICES)[sc.SETUP_INSTRUMENT["quality"]],
              dict(sc.WP_MODE_CHOICES)[sc.SETUP_INSTRUMENT["wp_mode"]]]
    for key, blob in before.items():
        assert all(w in blob for w in wanted), (
            f"the recorded {key} text no longer spells the three settings out, "
            "so it can no longer stand in for the card that did")
        assert "scenario" not in blob.lower(), (
            f"the recorded {key} text mentions a scenario; it is supposed to "
            "be the version that did not")


def test_the_printer_card_sends_the_user_to_the_scenario_not_the_tick_box():
    """Scenario 3 ticks "Profile my printer from this scan" for the user.

    Before this change the card's step 7 told them to tick it themselves,
    which is both longer and, once a scenario is in the window, the wrong
    instruction: the tick alone does not set the profile settings.
    """
    steps = _steps_text("printer_from_scan")
    assert "third usage scenario" in steps or "usage scenario" in steps, (
        "no step points at the scenario list")
    assert "tick “Profile my printer from this scan”" not in steps, (
        "a step still teaches the tick box instead of the scenario")


# --------------------------------------------- the window's own ⓘ is not stale
def test_the_window_help_leads_with_the_usage_scenario(dlg):
    """It is the first question on screen, so it is the first thing said."""
    from ui.dialogs.scanin_dialog import ScannerProfileDialog

    help_text = ScannerProfileDialog.HELP
    assert "Usage scenario: what is this profile for?" in help_text, (
        "the window's help does not name the row that is now at the top of it")
    labels = _scenario_labels(dlg)
    for key, label in labels.items():
        assert label in help_text, f"the help never quotes the {key} scenario"


def test_the_window_help_does_not_send_the_user_to_the_wrong_control():
    """The exact sentence that was false for fifty-five days."""
    from ui.dialogs.scanin_dialog import ScannerProfileDialog

    help_text = ScannerProfileDialog.HELP
    assert ("There are two ways to provide the target — choose one at the top "
            "of the window") not in help_text, (
        "the help still points at the top of the window for the SOURCE "
        "choice; the top of the window is the usage scenarios")


def test_the_window_help_names_the_build_button_in_both_of_its_states(dlg):
    """The button is renamed by `_apply_mode_title`, and the help named one
    state only — the one the reader is NOT looking at in printer mode."""
    from ui.dialogs.scanin_dialog import ScannerProfileDialog

    help_text = ScannerProfileDialog.HELP
    for wanted in ("Build profile with scanner or camera",
                   "Build printer profile"):
        assert wanted in help_text, (
            f"the help never names the button state {wanted!r}")
    # …and the window really does use both, so neither is a guess.
    dlg._printer_cb.setChecked(False)
    dlg._apply_mode_title()
    scanner_label = dlg._run_btn.text()
    dlg._mode_chromiq.setChecked(True)
    dlg._printer_cb.setChecked(True)
    dlg._apply_mode_title()
    printer_label = dlg._run_btn.text()
    dlg._printer_cb.setChecked(False)
    dlg._apply_mode_title()
    assert scanner_label != printer_label, (
        "the build button no longer changes with the mode, so this help "
        "sentence needs rewriting rather than this test relaxing")
    assert scanner_label in help_text and printer_label in help_text


def test_the_window_help_contents_list_is_in_the_real_order():
    """It promises "in order" and it used to be wrong in two ways: it listed
    capture before averaging, and the sections run the other way round."""
    from ui.dialogs import scanin_dialog as sd

    help_text = sd.ScannerProfileDialog.HELP
    tail = help_text[help_text.index("The sections below cover, in order:"):]
    listed = tail[:tail.index("\n\n")]
    # The four sections, in the order they are concatenated onto HELP.
    order = [sd.SCANNING_TIPS_HELP, sd.SCAN_SETUP_HELP, sd.CAMERA_HELP]
    at = [help_text.index(sec) for sec in order]
    assert at == sorted(at), "the sections are no longer in this order"
    # …and the sentence follows it: averaging first, then scanning, then camera.
    for a, b in (("best result", "how to scan"), ("how to scan", "camera")):
        assert listed.index(a) < listed.index(b), (
            f"the contents list puts {b!r} before {a!r}: {listed!r}")


# ------------------------------------------------- the note register is real
def test_every_note_is_a_heading_and_a_body():
    """The schema, checked on every card rather than only the two new ones."""
    for card in _cards():
        for i, step in enumerate(card.get("steps") or (), 1):
            assert len(step) <= 4, (
                f"{card['key']} step {i}: a step is (tab, text[, optional"
                "[, notes]])")
            for note in _notes_of(step):
                assert len(note) == 2, (
                    f"{card['key']} step {i}: a note is (heading, body)")
                heading, body = note
                assert isinstance(heading, str) and heading.strip()
                assert isinstance(body, str) and body.strip()
                assert len(heading) < 70, (
                    f"{card['key']} step {i}: a note heading is a label, not "
                    f"a sentence: {heading!r}")
                assert len(body) > len(heading), (
                    f"{card['key']} step {i}: a note shorter than its own "
                    "heading belongs in the step")


def test_the_two_scanner_cards_use_the_note_register():
    """Not decoration. These are the two cards Knut's instruction was about,
    and the point of the change is that their reasoning left the step list."""
    for key in SCANNER_CARDS:
        notes = [n for s in _card(key)["steps"] for n in _notes_of(s)]
        assert len(notes) >= 3, (
            f"{key} carries {len(notes)} notes; its explanations are still "
            "numbered steps")


@pytest.mark.parametrize("key", SCANNER_CARDS)
def test_no_step_of_these_cards_is_an_essay(key):
    """The measurable half of "simple steps".

    Before this change ``printer_from_scan`` step 2 ran to 200 words and step 3
    to 130, both of them explanation, both of them numbered. The longest step
    of these two cards is now well under that, and the reasoning is in notes,
    which is where a reader can leave it.
    """
    longest = max((str(s[1]) for s in _card(key)["steps"]), key=len)
    assert len(longest) <= 460, (
        f"{key} has a {len(longest)}-character step; if it explains rather "
        f"than instructs, it is a note:\n  {longest[:160]}…")


def test_a_note_is_never_the_only_place_a_warning_lives():
    """A note is CLOSED on screen. Anything a reader must not miss stays in
    the step, and the two cards' sharpest warning is the one about keeping the
    measuring profile separate."""
    for key in SCANNER_CARDS:
        assert "separate" in _steps_text(key)


# ------------------------------------------ a note is secondary, and it prints
def test_a_note_starts_closed_and_its_heading_is_a_button(_app):
    """Knut: *"if the user decides to want that"*. Closed until asked for."""
    from ui.dialogs.welcome_dialog import StepNote

    note = StepNote("Why this matters", "Because of the reason.")
    assert not note.is_open()
    # isVisibleTo, NOT isVisible. A widget whose parent was never shown reports
    # isVisible() False whatever its own flag says, so the first version of
    # this line passed with the note rendering OPEN: proved by mutating
    # `setVisible(False)` to `setVisible(True)`, which left it green.
    assert not note._body.isVisibleTo(note)
    btn = note.findChild(QPushButton, "welcome_note_head")
    assert btn is not None, "the heading is not a focusable control"
    assert "Why this matters" in btn.text()
    note.set_open(True)
    assert note.is_open()
    assert note._body.isVisibleTo(note), "opening the note showed nothing"
    note.set_open(False)
    assert not note._body.isVisibleTo(note)


def test_on_screen_a_note_is_dimmer_than_the_step_it_sits_under(_app,
                                                                tmp_path):
    """"Secondary" is a colour, not a wish. Checked in all three appearances,
    because a rule written for one theme has been wrong in another before."""
    from PyQt6.QtWidgets import QLabel

    from ui.dialogs.welcome_dialog import WelcomeDialog

    for mode in ("dark", "light", "neutral"):
        d = WelcomeDialog(_FakeSettings(), None, mode)
        d._on_card_clicked("printer_from_scan")
        step = d._steps_host.findChildren(QLabel, "welcome_step_body")
        note = d._steps_host.findChildren(QLabel, "welcome_note_body")
        head = d._steps_host.findChildren(QPushButton, "welcome_note_head")
        assert step and note and head, mode
        assert note[0].styleSheet() != step[0].styleSheet(), (
            f"{mode}: a note is painted in the step's own ink")
        assert "color:" in head[0].styleSheet(), (
            f"{mode}: the note heading was never tinted")
        d.close()
        d.deleteLater()


def test_a_note_prints_and_prints_as_a_note(_app):
    """Paper has nothing to click, so a note that did not print would be a
    note that had been deleted. It still has to READ as the quieter half."""
    from ui.help_card_print import _PRINT_CSS, card_html

    assert "p.note" in _PRINT_CSS, "the printed note has no style of its own"
    body_px = int(_PRINT_CSS.split("body {")[1].split("font-size:")[1]
                  .split("px")[0])
    note_px = int(_PRINT_CSS.split("p.note {")[1].split("font-size:")[1]
                  .split("px")[0])
    assert note_px < body_px, (
        f"a printed note is {note_px} px against the body's {body_px}: it is "
        "not visibly secondary")

    # ESCAPED, because the printer escapes. `html.escape` turns an apostrophe
    # into `&#x27;`, so a raw substring search reports a note that is right
    # there in the markup as missing.
    import html as _html

    for key in SCANNER_CARDS:
        markup = card_html(_card(key))
        for step in _card(key)["steps"]:
            for heading, note_body in _notes_of(step):
                assert _html.escape(heading) in markup, (
                    f"{key}: note {heading!r} not printed")
                assert _html.escape(note_body[:40]) in markup, (
                    f"{key}: the body of note {heading!r} was dropped")
        assert 'class="note"' in markup


def test_a_card_with_no_notes_prints_exactly_as_it_did(_app):
    """The schema change had to be inert for the other nineteen cards.

    Proved here the way it was proved by hand: a card with no notes must
    produce markup containing no note paragraph at all, so nothing about the
    new register can leak into it.
    """
    from ui.help_card_print import card_html

    for card in _cards():
        if any(_notes_of(s) for s in card.get("steps") or ()):
            continue
        assert 'class="note"' not in card_html(card), (
            f"{card['key']} has no notes but printed one")
