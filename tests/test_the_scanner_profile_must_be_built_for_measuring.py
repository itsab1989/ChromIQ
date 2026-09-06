"""A scanner profile used as an instrument has to be BUILT as one, and until
beta 9 nothing in ChromIQ said so anywhere.

Knut, beta 9, having read the analysis and having written his own reference
``colprof`` command with ``-ua`` in it years ago:

    *"I totally forgot all this, and had to relearn all of it now, so this is
    really an important detail that the workflow steps in help cards and help
    descriptions must be clear about"*

ArgyllCMS's Scenarios page:

    *"If the purpose of the input profile is to use it as a substitute for a
    colorimeter, then the -ua flag should be used to force Absolute
    Colorimetric intent, and avoid clipping colors above the test chart white
    point. Unless the shaper/matrix type profile is a very good fit, it is
    probably advisable to use a LUT type profile in this situation."*

Both halves of that sentence are settings ChromIQ gets wrong by default for
this job: ``PTYPE_DEFAULT[False]`` is ``"s"`` (shaper + matrix) and the
quality default is ``"m"``.

**Measured here, 2026-09-05**, on Knut's own 864-patch IT8 scan, six profiles
built from one ``.ti3`` and looked up the way ``scanin`` looks them up
(``xicclu -ff -ia -px``; ``scanin.c:1029`` asks for ``icAbsoluteColorimetric``
with an XYZ override, hard-coded):

* **cLUT — Lab table, default white point: the table FLATTENS.** Device 0.76 /
  0.80 / 0.85 / 0.90 / 1.00 all read Y ≈ 0.833 — one colour. With ``-ua`` they
  read 0.915 / 0.973 / 1.009 / 1.009 / 1.009. Everything on a printed sheet
  brighter than the target's own white board is measured as the same colour,
  and no later step recovers it.
* **cLUT — XYZ table: no flattening** (0.917 → 1.624 over the same range).
  ``-ua`` changes what ChromIQ measures by about 0.5 ΔE00 over a test grid.
* **Accuracy** (report Part 5, same scan): ``-ax -qm`` 0.484 ΔE00 against
  ``-as -qm`` 0.913; ``-ax -qh`` 0.337 — Quality High is worth ~30 %, more
  than any white-point option.

So the help must name all three settings — type, quality, white point — and it
must do so **where somebody meets them in the flow**, not only behind an ⓘ.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel  # noqa: E402

from core.settings import DEFAULTS  # noqa: E402

#: The three settings a scanner profile needs to be an instrument, as they are
#: spelled ON SCREEN. Taken from `scanner_colprof.PTYPE_CHOICES` /
#: `QUALITY_CHOICES` / `WP_MODE_CHOICES`, not from memory.
_XYZ_CLUT = "cLUT — XYZ table"
_LAB_CLUT = "cLUT — Lab table"
_UA = "Force Absolute Colorimetric (-ua)"


class _FakeSettings:
    def __init__(self, **overrides):
        import tempfile
        self._store = {**DEFAULTS, **overrides}
        if not self._store.get("custom_output_path"):
            self._store["custom_output_path"] = tempfile.mkdtemp(
                prefix="chromiq-bj-")

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, value):
        self._store[key] = value


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def _out_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("bj-ua-help")


@pytest.fixture
def dlg(_app, _out_dir):
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    d = ScannerProfileDialog(object(), _FakeSettings(
        custom_output_path=str(_out_dir)))
    yield d
    d.deleteLater()


def _tip(d, title):
    from ui.tooltip_button import TooltipButton
    return next((t._body for t in d.findChildren(TooltipButton)
                 if t._title == title), None)


# -------------------------------------------------- the labels really exist
def test_the_three_settings_are_named_the_way_the_window_spells_them():
    """If a combo entry is ever reworded, the help must be reworded with it —
    otherwise it sends the user looking for a control that is not there."""
    from ui.dialogs import scanner_colprof as sc
    assert _XYZ_CLUT in dict(sc.PTYPE_CHOICES).values()
    assert _LAB_CLUT in dict(sc.PTYPE_CHOICES).values()
    assert _UA in dict(sc.WP_MODE_CHOICES).values()
    assert "High" in dict(sc.QUALITY_CHOICES).values()
    # …and the reason the help is needed at all: none of the three is default.
    assert sc.PTYPE_DEFAULT[False] == "s", "scanner default is shaper+matrix"
    assert dict(sc.WP_MODE_CHOICES)[""].startswith("Map chart white")


# ------------------------------------------------------- the printer-mode ⓘ
def _bullet(body, head):
    """One "• …" bullet of a help body, from *head* to the next blank line.

    Slicing to the END of the text instead would let a claim removed from the
    bullet be "found" three paragraphs later — which is exactly how four
    mutations of this file's own subject slipped through on the first pass."""
    i = body.index(head)
    j = body.find("\n\n", i)
    return body[i:j if j != -1 else len(body)]


def test_the_printer_mode_help_names_all_three_settings(dlg):
    body = _tip(dlg, "Printer profile from a scan")
    assert body, "the printer-mode help has gone"
    assert "-ua" in body
    assert _XYZ_CLUT in body
    assert "Quality" in body
    for word in ("absolute colorimetric",):
        assert word in body.lower(), f"{word!r} is never glossed"
    # Each of the three is its own instruction, and each has to name the
    # control it is about — in its OWN bullet.
    assert _XYZ_CLUT in _bullet(body, "• Profile type")
    assert "High" in _bullet(body, "• Quality")
    wp = _bullet(body, "• Advanced")
    assert "White Point Handling" in wp
    # The INSTRUCTION has to carry the flag, spelled the way the combo spells
    # it. "-ua" appearing anywhere in the bullet is not enough: the ArgyllCMS
    # quotation inside the same bullet also contains it, so a bullet that told
    # you to pick the wrong entry would still have passed.
    assert _UA in wp, f"the bullet does not name {_UA!r}: {wp!r}"


def test_the_printer_mode_help_warns_about_the_lab_table(dlg):
    """The one case where the default is not merely less good but destructive."""
    body = _tip(dlg, "Printer profile from a scan")
    lab = _bullet(body, "• Profile type")
    assert _LAB_CLUT in lab, "the Lab table is not warned about where it is chosen"
    assert "Do NOT" in lab or "do not" in lab
    assert "lighter" in lab or "brighter" in lab
    assert "same colour" in lab


def test_the_printer_mode_help_quotes_argylls_own_instruction(dlg):
    """Ours is not the only voice saying this, and the user can check it."""
    body = _tip(dlg, "Printer profile from a scan")
    assert "substitute for a colorimeter" in body
    assert "clipping colors above the test chart white point" in body


def test_the_printer_mode_help_is_honest_about_the_size_of_the_gain(dlg):
    """Measured, `-ua` changes ChromIQ's OWN reading of an XYZ-cLUT profile only
    a little, because scanin already reads absolutely. Overselling it would be
    the same fault in the other direction."""
    body = _tip(dlg, "Printer profile from a scan")
    assert "absolute" in body.lower()
    assert "Quality" in body
    # The bigger lever must be presented as the bigger lever.
    assert "biggest" in body or "30 %" in body


# ------------------------------------- where the scanner profile is CHOSEN
def test_the_scanner_profile_help_repeats_the_requirement(dlg):
    """This ⓘ sits on the control where the .icc is picked — the last moment a
    user can still fix it."""
    body = _tip(dlg, "Scanner profile")
    assert body
    assert "-ua" in body and _XYZ_CLUT in body and "High" in body
    assert _LAB_CLUT in body, "the destructive case is not named here"


def test_ticking_the_box_says_the_requirement_without_being_asked(dlg):
    """Knut wrote the flag into his own reference command, annotated why, and
    still forgot it. Help nobody opens is help nobody has — so the moment
    printer mode goes on, ChromIQ says what the scanner profile has to be.

    It lands in the LOG rather than as a label in the panel, and that is a
    measured constraint, not a preference: on a 1079-px screen the window is
    already capped at 934 px and the left column gets 696 px against a 709-px
    sizeHint, so a wrapping hint under the scanner-profile field was drawn
    through the field above it and the label below (three overlapping widget
    pairs, against none without it). What matters for this test is that the
    user is told unprompted, and told all three settings."""
    dlg._mode_chromiq.setChecked(True)
    dlg._log.clear()
    dlg._printer_cb.setChecked(True)
    said = dlg._log.toPlainText()
    assert said.strip(), "ticking the box says nothing at all"
    assert "-ua" in said
    assert _XYZ_CLUT in said and "High" in said
    assert "Advanced" in said, "the user is not told where the setting lives"
    assert "default" in said, (
        "it does not say that this is NOT what ChromIQ would do on its own")


def test_it_is_not_repeated_when_the_box_is_switched_off(dlg):
    """A note that reappears on every toggle is noise."""
    dlg._mode_chromiq.setChecked(True)
    dlg._printer_cb.setChecked(True)
    dlg._log.clear()
    dlg._printer_cb.setChecked(False)
    assert "-ua" not in dlg._log.toPlainText()


# ------------------------------------------------------------- help cards
def _card(key):
    from ui.dialogs.welcome_dialog import WORKFLOWS
    return next(c for c in WORKFLOWS if c.get("key") == key)


def _steps_text(key) -> str:
    """Only what a numbered STEP says. The instruction, not its reasoning."""
    return " ".join(str(s[1]) for s in _card(key)["steps"])


def _card_text(key) -> str:
    """Everything on the card: the steps AND the notes under them.

    THE NOTES ARE PART OF THE CARD, and this helper had to learn that.
    2026-09-06 gave a step an optional fourth element, a sequence of
    ``(heading, body)`` notes, on Knut's instruction: *"A user should be guided
    with simple steps, and given the more detailed explanations as notes for a
    deeper understanding, if the user decides to want that."* Everything below
    that reads like an explanation rather than an action moved into one, so a
    check that reads ``s[1]`` alone would report a card that had lost the very
    facts it still carries. It is closed on screen and printed in full, which
    is why it counts.
    """
    parts = []
    for step in _card(key)["steps"]:
        parts.append(str(step[1]))
        for heading, body in (step[3] if len(step) > 3 else ()):
            parts += [str(heading), str(body)]
    return " ".join(parts)


def test_the_printer_from_scan_card_names_all_three_settings():
    """Knut's words: the *workflow steps in help cards* must be clear about it.
    Before beta 9 this card mentioned neither the flag, nor the profile type,
    nor even Quality."""
    blob = _card_text("printer_from_scan")
    assert "-ua" in blob
    assert _XYZ_CLUT in blob
    assert "Quality" in blob and "High" in blob
    assert "Advanced" in blob


def test_the_step_itself_still_says_to_build_it_for_measuring():
    """The three settings may live in a note; the INSTRUCTION may not.

    The other half of the rule the note register introduced. A reader who never
    opens a note must still be told, in the numbered step, that the scanner
    profile has to be built as a measuring instrument and which scenario does
    it. Otherwise "moved to a note" is indistinguishable from "deleted".
    """
    step_one = str(_card("printer_from_scan")["steps"][0][1])
    assert "MEASURING" in step_one, (
        "the first step no longer says what kind of profile this is")
    assert "measuring instrument" in step_one, (
        "the first step does not name the scenario that builds one")


def test_the_printer_from_scan_card_explains_why_before_it_instructs():
    """A step that only says "tick this" is the step people skip."""
    blob = _card_text("printer_from_scan")
    assert "84 %" in blob, "the target-white-vs-paper-white fact is not given"
    assert _LAB_CLUT in blob
    assert "perfect white surface" in blob


def test_the_scanner_profile_card_points_at_the_measuring_settings():
    """The card that BUILDS the profile is the one where the settings are
    actually entered, so it cannot be silent about them either."""
    blob = _card_text("scanner_profile")
    assert "-ua" in blob
    assert _XYZ_CLUT in blob
    assert "flatbed scanner" in blob, (
        "the card does not connect this to the printer workflow it serves")


def test_both_cards_say_the_measuring_profile_is_a_separate_file():
    """It makes everyday scans dark and tinted. A user who overwrites their
    normal scanner profile with it has broken their scanning, and would have no
    idea why."""
    for key in ("printer_from_scan", "scanner_profile"):
        blob = _steps_text(key)
        assert "separate" in blob, (
            f"{key} does not say to keep it separate in a STEP — a warning "
            f"this sharp cannot sit behind a disclosure")
