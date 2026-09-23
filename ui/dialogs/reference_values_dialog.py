"""One window for every set of numbers ChromIQ reads but may not ship.

**WHY THIS EXISTS AT ALL.** ChromIQ reads two kinds of other people's
published data, and this is the one door to both.

* The ISO 12647 tolerance limits, which ChromIQ may NOT ship: they are the
  content of a paid standard, so a licence holder supplies their own copy and
  ChromIQ reads it.
* Fogra's reference data, which ChromIQ DOES ship, under a grant that allows
  it. Nothing has to be supplied and the app works offline out of the box. What
  a user may still do is point ChromIQ at a NEWER file, per set, for the day
  Fogra revises a printing condition or publishes one this build never heard
  of. Sebastian, 2026-09-20: *"we could ship the most recent version and allow
  for a way to use newer values if they are released at some point in the
  future without relying on an update to ChromIQ for it."*

The two need different controls, and generalising the second on to the first is
what :class:`Template` and :class:`Supplied` are for: a source may offer "use a
newer file" without offering "save a file to fill in", and may supply a dozen
independently versioned things rather than one. Beta 26 gave that three buttons in the Report limits window,
and Basti, 2026-09-20, saw where it was going: *"if you are putting in 3 more
buttons there will be quite a lot in the end"*.

He is right, and the arithmetic is the argument: one data source cost three
buttons, so two sources cost six, in a window whose subject is a table of
limits and not a file manager. **One door, and a small window behind it with a
section per source.** Adding Fogra is then a new entry in `SOURCES` and nothing
in the Report limits window changes at all.

The window also does something the row of buttons could not: it SAYS WHAT IS IN
USE. A button cannot tell you that ChromIQ is judging against your own file,
and that is the one fact a person opening this wants first.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout,
                             QLabel, QPushButton, QScrollArea, QVBoxLayout,
                             QWidget)

from core.i18n import tr
from ui.styles import SPEC_GREEN
from ui.theme import panel_border_qss
from ui.tooltip_button import TooltipButton

#: How a control in here is made short, and it is NOT ``setFixedHeight``.
#:
#: Basti asked twice: *"the three buttons should be reduced in heigth"*, then
#: *"the current ones are still big ... they could be smaller i think"*. Beta 26
#: answered with a fixed height of 22 and this window first answered with one of
#: 18, and BOTH ARE 42 px ON SCREEN. `ui/styles.py` sets
#: `QPushButton { padding: 6px 18px; min-height: 28px; }` for the whole app, and
#: Qt's stylesheet style folds that into `minimumSizeHint` (28+6+6+1+1 = 42),
#: which a layout honours over a fixed height. A fixed height therefore cannot
#: make ANY button in ChromIQ shorter than 42 px, and the guard that read
#: `.height()` off a dialog nobody showed read back the 18 nobody sees.
#:
#: A per-widget stylesheet can, because it puts `min-height` DOWN as well as
#: capping `max-height`. This is the declaration the Report limits window's own
#: "Restore defaults" button already uses, and it measures 22 px, which is
#: what the preset window's button settled on (B8-420).
#:
#: Measured on screen, round 30, `scripts/adv30_eighteen_px_is_forty_two.py`;
#: guarded by `tests/test_a_short_button_is_short_on_screen.py`, which lays the
#: button out under the app's own stylesheet before it measures anything.
SMALL_BTN_QSS = ("QPushButton { padding: 1px 6px; font-size: 10px;"
                 " min-height: 22px; max-height: 22px; }")

#: The width the window opens at. Wide enough that the per-set lines and the
#: paragraphs above them sit on one line each in every language the catalogues
#: carry, which is what makes the height below honest.
_DEFAULT_WIDTH = 820


@dataclass(frozen=True)
class Supplied:
    """One thing a source supplies, and which copy of it is in force.

    **A SOURCE IS NOT ALWAYS ONE FILE, AND THE WINDOW HAD ASSUMED IT WAS.**
    The ISO values are a single table: one file in, one file out, one sentence
    about it. Fogra's reference data is eleven printing conditions that are
    published, revised and withdrawn independently of each other, and a user
    who has downloaded a newer FOGRA51 has not thereby said anything about
    FOGRA52. So "which copy is in force" is a question per SET, "Stop using
    it" is an action per SET, and a single state line for the source could
    answer neither.

    ISO supplies exactly one of these, so its section looks and behaves as it
    did: one line, one Stop button beside it.
    """

    key: str
    #: The sentence the window shows. Already translated.
    line: str
    #: True when the copy in force is the user's, which is the only case where
    #: there is anything for "Stop using it" to remove.
    is_yours: bool
    forget: Callable[[], bool]
    #: A SECOND, QUIETER LINE UNDER THE FIRST, or "" for no second line.
    #:
    #: It exists because the two lines answer two different questions and only
    #: one of them is ChromIQ's to answer. The first says which copy is in
    #: force, which ChromIQ knows. The second quotes what a file the user
    #: supplied says about ITSELF, which ChromIQ has not checked.
    #:
    #: **AND BECAUSE ONE LINE COULD NOT HOLD BOTH.** Folded together they made
    #: 108 characters, which wraps at every width this window has, and a
    #: wrapped row here paints its second line across the row beneath it:
    #: measured on screen, challenge round 31, in both languages, with
    #: "und ist datiert auf May 2015." drawn over the FOGRA47 line.
    detail: str = ""
    #: Whether the line may wrap, and IT IS NOT A STYLE CHOICE.
    #:
    #: A word-wrapped `QLabel` reports a sizeHint of TWO lines at its own
    #: natural width, and a layout adds those up whatever width the window is
    #: actually given. Measured on screen 2026-09-20 with twelve Fogra rows:
    #: each row is 23 px tall and claims 48, so the window opened 350 px
    #: taller than its content and a third of it was empty.
    #:
    #: So a line that CAN be long wraps -- ISO's says "In use:" and a file path
    #: -- and a line that cannot does not. Fogra's is a fixed sentence of a set
    #: name, a version and a date, and it has no path in it.
    wraps: bool = True


@dataclass(frozen=True)
class Template:
    """The "save a file to fill in" half, for a source that HAS one.

    **Fogra has nothing to fill in, and that is why this is a separate
    object.** The ISO values are numbers ChromIQ may not ship, so it writes a
    skeleton with the rows named and the values left blank and the licence
    holder types them in. Fogra publishes complete files; there is no skeleton
    to write, nothing for a user to type, and a button offering to write one
    would be an instruction to do something that does not exist.

    A source with ``template=None`` shows two buttons instead of three.
    """

    label: str
    #: The name the file dialog starts with.
    name: str
    write: Callable[[Path], None]


@dataclass(frozen=True)
class Source:
    """One set of numbers somebody else publishes and ChromIQ reads."""

    key: str
    title: str
    why: str
    #: The ⓘ text for this source. Already translated.
    help_text: str
    #: Where ChromIQ keeps its OWN copies of this source, for the file
    #: dialogs' sidebar shortcut.
    own_dir: Callable[[], Path]
    #: What this source supplies, and which copy of each is in force.
    items: Callable[[], "list[Supplied]"]
    #: Install the file the user chose. Returns the sentence to show them.
    #: Raises ``OSError`` or ``ValueError`` with a readable reason.
    install: Callable[[Path], str]
    install_label: str
    #: The file dialog's own title. A SEPARATE KEY, not `install_label` with
    #: its ellipsis stripped: a derived string is invisible to
    #: `scripts/i18n_extract.py` (the `tr(var)` blind spot), and stripping "…"
    #: is a guess about punctuation in thirteen languages.
    pick_title: str
    forget_label: str
    #: What to say once one item has been given up, given that item's key.
    #:
    #: **A SOURCE OWNS THIS SENTENCE BECAUSE ONLY THE SOURCE KNOWS WHAT IS LEFT
    #: BEHIND.** It used to be one static method on the window that branched on
    #: `template is not None`, which is a question about buttons, and for Fogra
    #: it answered "ChromIQ is back to the copy of FOGRA61 that shipped with
    #: it" -- about the one set in the archive that ships nowhere, which is the
    #: very case this whole feature exists for. Measured challenge round 31:
    #: after that sentence `by_id("FOGRA61")` is None and the row is gone from
    #: the window the sentence is standing in front of.
    forgotten: "Callable[[str], str] | None" = None
    #: None when the source has nothing to fill in. See :class:`Template`.
    template: "Template | None" = None
    #: Show a greyed "Stop using it" on an item that has nothing to stop.
    #:
    #: True for a source with ONE item, where the button is part of the
    #: three-step story the ⓘ tells and a reader looking for it must find it.
    #: False for one with a dozen, where eleven dead buttons is not a window,
    #: it is a wall: the button appears on the set it can act on.
    always_show_forget: bool = True
    #: What the file is called in a file dialog's filter
    file_filter: str = "JSON files (*.json)"


def iso_source() -> Source:
    from workflow import compliance_sets as cs

    def items() -> "list[Supplied]":
        where = cs.iso_data_path_text()
        line = (tr("In use: {path}").format(path=where) if where else
                tr("Nothing supplied, so ChromIQ uses its own numbers and "
                   "shows ? where it has none."))
        # `in_use` is the wrong question for the BUTTON. It answers "is
        # ChromIQ judging against somebody's numbers", and
        # `CHROMIQ_COMPLIANCE_ISO_FILE` makes that true without there being
        # anything here to remove -- `forget_user_values` only ever deletes
        # ChromIQ's OWN copy, returns False, and nothing refreshes. The button
        # then sat enabled and did NOTHING when pressed, which is the fault
        # beta 26 shipped three times over (B8-511). Ask the question the
        # button actually answers.
        return [Supplied(key="iso12647", line=line,
                         is_yours=cs.user_values_path().is_file(),
                         forget=cs.forget_user_values, wraps=True)]

    def install(path: Path) -> str:
        # A SENTENCE CHROMIQ WROTE, NEVER A PYTHON EXCEPTION (B8-548).
        # `install_user_values` calls `json.loads(read_text(encoding="utf-8"))`
        # and both of its failures are ValueError, so the caller's generic
        # branch caught them and printed the exception verbatim. Picking a
        # `.zip` in this half of the window produced "ChromIQ could not read
        # that file: 'utf-8' codec can't decode byte 0xe2 in position 10:
        # invalid continuation byte", measured on screen in challenge round 31.
        # The Fogra half of the same window answers the same file with a
        # sentence naming what was wrong; this is that shape.
        try:
            dst = cs.install_user_values(path)
        except UnicodeDecodeError:
            raise ValueError(tr(
                "That file is not text ChromIQ can read. The values file is "
                "the one ChromIQ writes for you with “Save a file to fill "
                "in”, filled in with a text editor, and this looks like a "
                "program or an archive instead.")) from None
        except json.JSONDecodeError as exc:
            raise ValueError(tr(
                "That file is text, but it is not laid out the way ChromIQ "
                "wrote it (line {line}: {why}). Start again from “Save a file "
                "to fill in” and change only the numbers, leaving the "
                "punctuation as it is.").format(line=exc.lineno,
                                                why=exc.msg)) from None
        return tr("ChromIQ is using {path} now. Close and reopen the Report "
                  "limits window to see the values in the table."
                  ).format(path=dst)

    def forgotten(_key: str) -> str:
        # "its own numbers" was the shipped state's word for "?" in the two
        # ISO columns; once a set ships (#182 S-2, §23) what comes back is
        # that standard's shipped values, which are not ChromIQ's own.
        return tr("ChromIQ is back to what it ships. Close and reopen "
                  "the Report limits window to see the table change.")

    # WHAT SHIPS DECIDES THE FIRST SENTENCE (#182 S-2, §23). "ChromIQ does not
    # ship these numbers and cannot" is true only while the shipped file is
    # empty, so it is asked, not assumed.
    shipped = cs.shipped_iso_sets()
    if shipped:
        names = [tr(cs.SET_BY_ID[sid].label) for sid in shipped]
        if len(names) == 1:
            why = tr("ChromIQ ships the published values of “{name}”, so "
                     "that column judges without anything from you. If you "
                     "hold a copy of either standard, a value you supply from "
                     "it takes the place of ChromIQ's for that row, and a "
                     "column ChromIQ ships no values for stops showing ? and "
                     "starts judging.").format(name=names[0])
        else:
            why = tr("ChromIQ ships the published values of both ISO columns, "
                     "so they judge without anything from you. If you hold a "
                     "copy of either standard, a value you supply from it "
                     "takes the place of ChromIQ's for that row.")
    else:
        why = tr("ChromIQ does not ship these numbers and cannot: they are the "
                 "content of a paid standard. Supply your own copy's values "
                 "and the two ISO columns stop showing ? and start judging.")

    return Source(
        key="iso12647",
        title=tr("ISO 12647-7 and ISO 12647-8 limit values"),
        why=why,
        help_text=tr(
            "Three steps, and no typing of file paths:\n\n"
            "1.  Press “Save a file to fill in” and choose where to "
            "keep it. ChromIQ writes a file listing every value it can use, "
            "in the order the table shows them, with the numbers left "
            "blank.\n"
            "2.  Open that file in any text editor and type the numbers from "
            "your own copy in place of the word null. A value you leave alone "
            "keeps what the table shows for it now, so you can do a few at a "
            "time.\n"
            "3.  Press “Use a file I filled in” and pick it. ChromIQ "
            "copies it into its own folder, so the values stay even if you "
            "tidy the file away afterwards.\n\n"
            "“Stop using it” removes ChromIQ's copy and goes back to what "
            "ChromIQ ships. The file you made it from is never touched.\n\n"
            "The values stay on this computer. ChromIQ does not send them "
            "anywhere, they are not part of a report you share, and they are "
            "not written into any project."),
        own_dir=lambda: cs.user_values_path().parent,
        items=items,
        install=install,
        install_label=tr("Use a file I filled in…"),
        pick_title=tr("Use a file I filled in"),
        forget_label=tr("Stop using it"),
        forgotten=forgotten,
        template=Template(label=tr("Save a file to fill in…"),
                          name=cs.ISO_USER_FILE,
                          write=lambda p: p.write_text(cs.iso_values_template(),
                                                       encoding="utf-8")),
        file_filter="JSON files (*.json)",
    )


def fogra_source() -> Source:
    """Fogra's reference data, which ChromIQ DOES ship, and which the user may
    still replace with a newer file.

    **THE OTHER SHAPE OF THE SAME PROBLEM, AND THE REASON THIS WINDOW IS NOT A
    FILE MANAGER FOR MISSING NUMBERS.** The ISO values are absent because
    ChromIQ may not ship them. Fogra's are present, under a grant that allows
    it, and the thing that goes stale is not the permission but the archive:
    Fogra revises a printing condition, publishes a set ChromIQ has never heard
    of, or promotes one out of beta, and none of that waits for a ChromIQ
    release. Sebastian, 2026-09-20: *"we could ship the most recent version and
    allow for a way to use newer values if they are released at some point in
    the future without relying on an update to ChromIQ for it."*

    So there is no template here, and there is no "nothing supplied" state
    either: every set always has a copy in force, and the only question is
    whose.
    """
    from workflow import reference_sets as rs

    def items() -> "list[Supplied]":
        # THE SENTENCE COMES FROM `reference_sets`, NOT FROM HERE. This window
        # used to build the same three sentences a second time, so the guard on
        # `in_force_lines` measured a function nothing on screen called. One
        # implementation, and a guard on it is a guard on the window.
        out: "list[Supplied]" = []
        # BY SET NUMBER, AND THE MODULE DECIDES THAT, NOT THIS WINDOW.
        # `rs.in_window_order` is what `in_force_lines()` iterates too, so the
        # two cannot drift apart; sorting here alone reddened the guard that
        # exists to keep them one implementation (B8-544, B8-554).
        for s in rs.in_window_order(rs.available()):
            out.append(Supplied(
                key=s.id, line=rs.in_force_line(s),
                detail=rs.what_the_file_says(s),
                is_yours=s.supplied_by_user,
                forget=lambda i=s.id: rs.forget_user_set(i),
                wraps=False))
        return out

    def install(path: Path) -> str:
        ids = rs.install_user_file(path)
        if len(ids) == 1:
            return tr("ChromIQ is using your copy of {name} now. Everything "
                      "else is unchanged.").format(name=ids[0])
        return tr("ChromIQ is using your copies of these {count} sets now: "
                  "{names}. Everything else is unchanged."
                  ).format(count=len(ids), names=", ".join(sorted(ids)))

    def forgotten(key: str) -> str:
        """What is left once the user's own copy of one set is gone.

        **TWO ANSWERS, BECAUSE THERE ARE TWO OUTCOMES.** For a set ChromIQ
        ships, the place the file stood in is filled again by the file that
        shipped, and the old single sentence said so correctly. For a set it
        ships nothing for, the place is now empty and the set is not offered at
        all: `by_id` returns None and the row the user just pressed is gone
        from the window. FOGRA61 is exactly that case and is the case this
        feature was built for, so the sentence it produced was untrue about the
        one set that proves the design.
        """
        if rs.by_id(key) is None:
            return tr("ChromIQ is no longer using your copy of {name}. It "
                      "ships no copy of that set, so {name} has gone from the "
                      "list until you supply a file for it again. Your own "
                      "file is untouched.").format(name=key)
        return tr("ChromIQ is back to the copy of {name} that shipped with "
                  "it. Your own file is untouched.").format(name=key)

    return Source(
        key="fogra",
        title=tr("FOGRA reference sets"),
        why=tr("ChromIQ ships these and works without a download, so there is "
               "nothing you have to do here. If Fogra publishes a newer file, "
               "or one for a set ChromIQ does not ship, point ChromIQ at it "
               "and it will use yours instead for that set."),
        help_text=tr(
            "A reference set is a table of aim colours: what each patch of a "
            "named printing condition was supposed to look like. Fogra calls "
            "the same thing characterisation data, and the files are "
            "published at fogra.org.\n\n"
            "ChromIQ ships Fogra's own files and uses them unchanged, so you "
            "need nothing from this window to get started. It is here for the "
            "day the archive moves on:\n\n"
            "1.  Press “Use a newer file” and pick either a single "
            ".txt file or the .zip exactly as you downloaded it. ChromIQ "
            "copies it into its own folder, reads which set it is out of the "
            "file itself, and uses yours for that set from then on.\n"
            "2.  A set ChromIQ does not ship at all can arrive the same way. "
            "FOGRA61 is still beta in Fogra's archive, so ChromIQ ships "
            "nothing for it, and a file you supply is the only copy there "
            "will be.\n"
            "3.  “Stop using it” beside a set removes ChromIQ's copy of your "
            "file and goes back to the file that shipped. Your own download "
            "is never touched.\n\n"
            "ChromIQ records what you supplied, when, and what the file's "
            "checksum was at that moment, and it says so wherever the set is "
            "credited. It does not present a file you supplied as one it "
            "checked against the publisher, because it did not.\n\n"
            "The files stay on this computer. ChromIQ does not send them "
            "anywhere."),
        own_dir=rs.user_dir,
        items=items,
        install=install,
        install_label=tr("Use a newer file…"),
        pick_title=tr("Use a newer file"),
        forget_label=tr("Stop using it"),
        forgotten=forgotten,
        template=None,
        always_show_forget=False,
        file_filter="Reference data (*.txt *.zip)",
    )


def sources() -> "list[Source]":
    """Every source, in the order the window shows them."""
    return [iso_source(), fogra_source()]


class ReferenceValuesDialog(QDialog):
    """Supply, replace or remove the data ChromIQ reads but did not write."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Reference values"))
        self.setMinimumWidth(620)
        #: ``(source, item key, state label, Stop button)``, one per thing a
        #: source supplies. Rebuilt whenever the set of items changes.
        self._rows: "list[tuple[Source, str, QLabel, QPushButton]]" = []
        self._item_boxes: "dict[str, QVBoxLayout]" = {}
        self._sources: "list[Source]" = sources()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 14)
        outer.setSpacing(12)

        # THE CONTENT SCROLLS, AND ON ELEVEN SETS IT NEVER HAS TO.
        #
        # B8-547, challenge round 31, measured on screen: the eleven shipped
        # sets open this window at 626 px. Install Fogra's published archive,
        # which the ⓘ text tells the user to drop in exactly as downloaded, and
        # 22 sets at two lines each make it **1376 px against 1079 px of
        # screen**; macOS clamps the height and the rows then overlap, 231
        # overlapping pairs measured in German. The Close button was below the
        # bottom of the display.
        #
        # A cap on its own would have hidden rows with no way to reach them,
        # which is worse than a window that is too tall. A scroll area is the
        # smallest thing that keeps every row reachable, and it is deliberately
        # invisible in the ordinary case: no frame, no horizontal bar, a
        # vertical one only when the content genuinely does not fit, and the
        # opening height still computed from the content. With what ChromIQ
        # ships, this window is the same window it was.
        body = QWidget(self)
        inner = QVBoxLayout(body)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(12)

        head = QLabel(tr(
            "Some of what ChromIQ judges against was published by somebody "
            "else. Where ChromIQ may not ship it, supply your own copy here "
            "and it will be used. Where ChromIQ does ship it, you can still "
            "point it at a newer file. Everything you supply stays on this "
            "computer."), body)
        head.setWordWrap(True)
        inner.addWidget(head)

        for src in self._sources:
            inner.addWidget(self._section(src))
        inner.addStretch(1)

        self._scroll = QScrollArea(self)
        self._scroll.setWidget(body)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._body = body
        self._inner = inner
        outer.addWidget(self._scroll, 1)

        close = QPushButton(tr("Close"), self)
        close.clicked.connect(self.accept)
        self._close = close
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        outer.addLayout(row)
        self._refresh()

        # OPEN AT A SIZE WHERE THE HEIGHT IS THE CONTENT'S, NOT A HINT'S.
        #
        # `sizeHint()` asks every word-wrapped label how tall it is AT ITS OWN
        # NATURAL WIDTH, which is narrow, so three wrapping paragraphs each
        # claim two or three lines they will not use once the window is 800 px
        # across. Measured on screen 2026-09-20, before this: the window opened
        # 936 px tall over 580 px of content and a third of it was empty
        # nothing, under the Close button. `heightForWidth` asks the question
        # the window actually faces.
        self.resize(_DEFAULT_WIDTH, self._opening_height(outer))

    # ------------------------------------------------------------------
    def _opening_height(self, outer: QVBoxLayout) -> int:
        """As tall as the content wants, and never taller than the screen.

        The content's own answer first, because `sizeHint()` asks each
        word-wrapped label how tall it is at its NATURAL width, which is narrow,
        so three wrapping paragraphs each claim lines they will not use once the
        window is 820 px across. Measured 2026-09-20: 936 px asked for over 580
        px of content, a third of the window empty under the Close button.
        `heightForWidth` asks the question the window actually faces.

        Then the screen's answer, because the content's can exceed it (B8-547).
        The margin below leaves room for the menu bar and the dock without
        needing to know where either is; `availableGeometry` already excludes
        them where the platform reports them, and subtracting a little more
        costs nothing and covers the platforms that do not.
        """
        want = (self._inner.heightForWidth(_DEFAULT_WIDTH - 36)
                + outer.contentsMargins().top()
                + outer.contentsMargins().bottom()
                + outer.spacing()
                + self._close_row_height())
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return want
        return min(want, int(screen.availableGeometry().height() * 0.92))

    def _close_row_height(self) -> int:
        """What the Close button and its row occupy, measured and not assumed."""
        return max(28, self._close.sizeHint().height()) + 8

    def showEvent(self, event):                      # noqa: D401 - Qt override
        """Correct the opening height against the layout that actually ran.

        `_opening_height` predicts, and a prediction of a laid-out geometry is
        the thing this project keeps getting wrong. Constructed but unshown,
        this window reported 378 px of scrolling on content that fits, because
        its viewport was 30 px tall; shown, the same prediction was 4 px short,
        which is the scroll area's own chrome. Rather than carry a constant for
        that, the window asks once it has a layout: if anything is scrolled
        away and the screen has room, take the room.

        It only ever GROWS, and only up to the screen, so the archive case
        (B8-547) still stops at the display edge and still scrolls; and it runs
        once, so a user who resizes the window keeps their size.
        """
        super().showEvent(event)
        if getattr(self, "_height_settled", False):
            return
        self._height_settled = True
        hidden = self._scroll.verticalScrollBar().maximum()
        if hidden <= 0:
            return
        screen = self.screen() or QApplication.primaryScreen()
        room = (int(screen.availableGeometry().height() * 0.92) - self.height()
                if screen is not None else hidden)
        if room > 0:
            self.resize(self.width(), self.height() + min(hidden, room))

    # ------------------------------------------------------------------
    def _section(self, src: Source) -> QFrame:
        box = QFrame(self)
        box.setFrameShape(QFrame.Shape.StyledPanel)
        # Fusion draws a bare StyledPanel square; every other panel in ChromIQ
        # opts into a rounded one explicitly (B8-650) — see
        # `ui.theme.panel_border_qss`.
        box.setStyleSheet(panel_border_qss())
        col = QVBoxLayout(box)
        col.setContentsMargins(12, 10, 12, 10)
        col.setSpacing(6)

        title_row = QHBoxLayout()
        title = QLabel(f"<b>{src.title}</b>", box)
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(TooltipButton(src.title, self._help(src), box,
                                          min_width=520, color=SPEC_GREEN))
        col.addLayout(title_row)

        why = QLabel(src.why, box)
        why.setWordWrap(True)
        col.addWidget(why)

        # One row per thing this source supplies. Its contents are rebuilt by
        # `_fill_items`, because a source's list can GROW: installing Fogra's
        # FOGRA61 file adds a set that was not offered a moment ago.
        items = QVBoxLayout()
        items.setSpacing(2)
        items.setContentsMargins(0, 2, 0, 2)
        col.addLayout(items)
        self._item_boxes[src.key] = items

        btns = QHBoxLayout()
        btns.setSpacing(6)
        if src.template is not None:
            b = QPushButton(src.template.label, box)
            b.setStyleSheet(SMALL_BTN_QSS)
            b.clicked.connect(lambda _=0, s=src: self._template(s))
            btns.addWidget(b)
        use = QPushButton(src.install_label, box)
        use.setStyleSheet(SMALL_BTN_QSS)
        use.clicked.connect(lambda _=0, s=src: self._install(s))
        btns.addWidget(use)
        btns.addStretch(1)
        col.addLayout(btns)
        return box

    def _fill_items(self, src: Source) -> None:
        """Rebuild one source's per-item rows from what it says now."""
        box = self._item_boxes[src.key]
        while box.count():
            item = box.takeAt(0)
            sub = item.layout()
            if sub is not None:
                while sub.count():
                    w = sub.takeAt(0).widget()
                    if w is not None:
                        w.setParent(None)
                        w.deleteLater()
                sub.setParent(None)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._rows = [r for r in self._rows if r[0].key != src.key]
        parent = box.parentWidget() or self
        for it in src.items():
            line = QHBoxLayout()
            line.setSpacing(6)
            lbl = QLabel(it.line, parent)
            lbl.setWordWrap(it.wraps)
            lbl.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            line.addWidget(lbl, 1)
            stop = QPushButton(src.forget_label, parent)
            stop.setStyleSheet(SMALL_BTN_QSS)
            # THE BUTTON ANSWERS ITS OWN QUESTION, and B8-511 is what happens
            # when it answers a neighbouring one: "is ChromIQ using somebody's
            # numbers" is true in cases where there is nothing here to remove,
            # and the button then sat enabled over a slot that could do
            # nothing at all. `is_yours` is the question this button acts on.
            stop.setEnabled(it.is_yours)
            stop.setVisible(it.is_yours or src.always_show_forget)
            stop.clicked.connect(
                lambda _=0, s=src, k=it.key: self._forget(s, k))
            line.addWidget(stop, 0)
            box.addLayout(line)
            self._rows.append((src, it.key, lbl, stop))
            if it.detail:
                # ITS OWN ROW, NOT A WRAP. See `Supplied.detail`: a wrapped row
                # in this layout paints over the one beneath it, and two short
                # lines each fit on one at every width this window has.
                sub = QLabel(it.detail, parent)
                sub.setWordWrap(False)
                sub.setIndent(16)
                sub.setStyleSheet("color: palette(mid);")
                sub.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse)
                box.addWidget(sub)

    # ------------------------------------------------------------------
    @staticmethod
    def _help(src: Source) -> str:
        return src.help_text

    def _refresh(self) -> None:
        for src in self._sources:
            self._fill_items(src)

    def _refresh_later(self) -> None:
        """Rebuild AFTER the click that caused it has returned.

        `_fill_items` deletes the very button whose `clicked` handler is on the
        stack, and `_say` runs a modal loop inside that same handler. Deleting
        a widget from inside its own signal handler is the shape CLAUDE.md
        records as a segfault on this project (`ui/fade_scroll.py`, PyQt6
        6.11); `deleteLater` plus a zero timer means nothing is torn down until
        the stack is clear.
        """
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(0, self._refresh)

    def _say(self, text: str) -> None:
        from ui.tooltip_button import InfoDialog

        InfoDialog(tr("Reference values"), text, self, min_width=520).exec()

    def _template(self, src: Source) -> None:
        from PyQt6.QtCore import QStandardPaths

        from ui.widgets import save_file_dialog

        if src.template is None:                       # no button exists
            return
        docs = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation) or str(Path.home())
        # THE SIDEBAR SHORTCUT IS NOT DECORATION. Commit 758bfbbb added it to
        # both dialogs so a user could reach ChromIQ's own folder without
        # typing a path, and the move to one door dropped it from both. The
        # guard that was supposed to hold it read the slots' SOURCE, so it
        # could not notice (6d7b265c).
        where = save_file_dialog(
            self, tr("Save a file to fill in"), src.file_filter,
            start_path=str(Path(docs) / src.template.name),
            extra_paths=(str(src.own_dir()),))
        if not where:
            return
        try:
            src.template.write(Path(where))
        except OSError as exc:
            self._say(tr("That file could not be written: {error}")
                      .format(error=exc))
            return
        self._say(tr(
            "Saved to {path}. Open it in any text editor, type the numbers "
            "from your own copy in place of the word null, then come back and "
            "press “Use a file I filled in”.").format(path=where))

    def _install(self, src: Source) -> None:
        from PyQt6.QtCore import QStandardPaths

        from ui.widgets import open_file_dialog

        docs = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation) or str(Path.home())
        chosen = open_file_dialog(
            self, src.pick_title, src.file_filter,
            start_dir=docs,
            extra_paths=(str(src.own_dir()),))
        if not chosen:
            return
        try:
            said = src.install(Path(chosen))
        except ValueError as exc:
            # A SENTENCE A SOURCE WROTE IS SHOWN AS IT IS. Every ValueError out
            # of an installer here is written English: "That file is not a
            # reference data file…", "That file is not text ChromIQ can
            # read…". Wrapping one in "ChromIQ could not read that file:"
            # produced the doubled sentence photographed in the beta 29 drive,
            # *"ChromIQ could not read that file: That file is not text ChromIQ
            # can read."*, and the Fogra half of the window had been doing it
            # since b7475572.
            self._say(str(exc))
            return
        except OSError as exc:
            # An OSError is the operating system talking, not us, so it keeps
            # the frame that says who is speaking and why it is being quoted.
            self._say(tr("ChromIQ could not read that file: {error}")
                      .format(error=exc))
            return
        # Safe synchronously: this is the "Use a…" button's handler, and that
        # button is not one of the rows `_fill_items` rebuilds. The deferred
        # pass after `_say` is belt and braces for a source that ever changes
        # its own buttons.
        self._refresh()
        self._say(said)
        self._refresh_later()

    def _forget(self, src: Source, key: str = "") -> None:
        for it in src.items():
            if key and it.key != key:
                continue
            if it.forget():
                # NO SYNCHRONOUS REBUILD HERE. This runs inside the clicked
                # handler of the very button `_fill_items` destroys, and
                # `_say` opens a modal loop inside that same handler. The
                # rebuild is posted for after both have returned.
                self._say(self._forgotten_text(src, it.key))
                self._refresh_later()
            return

    @staticmethod
    def _forgotten_text(src: Source, key: str) -> str:
        """The source's own sentence, asked AFTER the item is gone.

        The order matters: `_forget` calls this once `it.forget()` has
        returned, so a source that has to look at what is left (Fogra does)
        sees the state the user is about to be shown, not the one before.
        """
        if src.forgotten is not None:
            return src.forgotten(key)
        return tr("ChromIQ is back to what it ships. Close and reopen "
                  "the Report limits window to see the table change.")
