# Which built-in presets the lists show: the gear, the window, the arrow (#182)

> These specifications are binding (CLAUDE.md, "The design specifications are
> binding"). Before changing the code this covers, read this file; a fault that
> contradicts it is reported, not simply fixed.
>
> **Status:** written 2026-09-24 for beta 42 from Knut's request in #182
> (comment 5818659478). Code: `core/curated_presets.py`,
> `ui/dialogs/builtin_presets_shown_dialog.py`, `ui/tabs/tab_chart.py`
> (`_populate_preset_combo`, `_on_preset_more_row`,
> `_open_builtin_presets_shown`, `_CappedComboBox`),
> `ui/builtin_preset_popup.py`, `scripts/make_preset_defaults.py`,
> `data/preset_defaults.json`. Tests: `tests/test_curated_builtin_presets.py`.

## ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.* Verified by driving the real app on screen
(proof in `~/Desktop/ChromIQ-beta42-proof/knut-k35-presets/`), which proves what
the app does; whether it is what it should do is Knut's or Sebastian's call.

### C1. The request, in Knut's words

> *"Users have complained that the current numbers of presets are too many and
> they want the amount reduced. This would though limit an advanced user to
> have larger charts available."*

Nothing is removed. Every built-in stays reachable from both lists.

### C2. The gear button

| Where | What |
|---|---|
| Create Chart, Manual, Presets frame, first row | a 28 px icon button with a gear, between "Open this tab's presets folder in {manager}" and the help icon, the same size and style as the folder button |
| its tooltip | "Choose which built-in presets are listed directly. The others stay available under an arrow in each group." |
| the frame's help icon | gains the line "⚙  Choose which built-in presets are listed directly; the others wait under an arrow (▸) in each group." |

`{manager}` is already the platform's own word (`core.platform_paths.
file_manager_name`: Finder on macOS, File Explorer on Windows, "your file
manager" on Linux), so Knut's side note about "Finder" was already met for this
button; see B8-1023 for the one other string that names Finder.

### C3. The window

* Title "Built-in presets in the lists"; modal.
* Three paragraphs: ticked presets are listed directly in "Select preset" and in
  the Built-in presets list (the middle of the three buttons at the top of
  Create Chart); the others wait under an arrow after the group's last ticked
  preset; the person's own presets are not affected and stay on top. The third
  paragraph ended "Your choice is kept when you close this window." until
  C3a below; it now ends "OK keeps your choice; Close leaves the lists as they
  were."
* Every built-in preset, and only built-ins, under the pulldown's own headings
  in the pulldown's own order, each with a tick box. A heading has a box of its
  own that ticks or clears its whole group (partly ticked when mixed) and says
  "N of M shown".
* ~~Only a Close button. Close, Escape and the window's close box all store the
  boxes as they are, and both lists are rebuilt at once.~~ **SUPERSEDED on
  2026-09-25 by Basti's decision, C3a below.** This was Knut's K35 wording
  (*"The window has only a Close button. Closing the window will automatically
  apply the changes."*, #182 5818659478).

### C3a. OK and Close (Basti, owner, 2026-09-25, B8-1097)

⏳ **Awaiting confirmation. Confirmed by:** *nobody yet.* Basti decided it; the
behaviour below is what the app does since B8-1097, proved on screen in
`~/Desktop/ChromIQ-beta43-proof/presets-ok-close/`, and awaits his
confirmation of the result (and Knut's, whose K35 rule it replaces).

Basti's decision, replacing Knut's "only a Close button; closing applies":

| Way out | What happens |
|---|---|
| **OK** (the default button, so Return on the list is OK) | the ticks are stored and both lists are rebuilt; the window closes |
| **Close** | the window closes; the ticks are discarded; the setting and both lists are unchanged |
| Escape | as Close |
| the window's close box | as Close |

* Two buttons at the bottom right, **OK to the LEFT of Close**, on macOS,
  Windows and Linux alike. They are placed by hand in a row of their own, not
  in a `QDialogButtonBox`: a button box orders by the style's
  `SH_DialogButtonLayout`, and the macOS and GNOME layouts put the accept
  button last (Close, OK). The shipped app pins the Windows layout through
  `WinButtonLayoutStyle` (`main.py`), so a button box would have come out
  right in the app, but the window no longer depends on that.
* The texts are the existing catalogue keys "OK" and "Close" (German "OK",
  "Schließen").

### C4. The two lists

Per group, in the group's usual order: the heading, the ticked presets, then an
arrow row "▸  N more presets" when anything is left over, then the rest. The
arrow points right while closed and down (▾) while open. A group with nothing
left over has no arrow. A group with nothing ticked shows the heading and the
arrow. The person's own presets stay at the very top of "Select preset",
untouched.

In "Select preset":

* The rest are hidden and cannot be stepped into with Up/Down or the wheel on
  the closed combo.
* A click on the arrow, or Return, Enter, Space or the Right arrow key on it,
  opens the group; Left closes it; Left on a revealed preset goes back up to
  its arrow. The list stays open and nothing is chosen.
* The arrow is never selected as a preset: it can only be reached while the
  list is open, and a selection that reaches the preset handler by any other
  road is put back.
* Opening the list while the selected preset is one under a closed arrow opens
  that arrow, so the list shows where the selection is.
  *Amended (challenge 3 of beta 42, B8-1032, not confirmed):* and the list
  is scrolled so the selected row is visible and highlighted wherever it is
  in the group (it stayed at the top of the group while the 33rd of 34
  revealed rows was selected).
* Which arrows are open lasts while the app runs; it is not a setting.

In the Built-in presets list (the ★/list button): the same rows and the same
arrow, which opens and closes without closing the list. That list now also
works by keyboard: Up and Down move, Return or Space picks a preset or opens an
arrow, Right and Left open and close an arrow, Escape closes.

"Which presets can be used for verification" is not changed, and "Compare with
profile" gets no arrow: Knut named the two lists above. "Compare with profile"
does follow the same ORDER (a group's ticked presets first, then the rest, all
shown), because it has read Create Chart's order since beta 41 (Basti: one
function answers the order for both).

### C5. What is shipped ticked, and why a later release does not overwrite a choice

* The shipped list is the data file `data/preset_defaults.json`, keyed by the
  preset's key (its identity), written by `scripts/make_preset_defaults.py`.
  The same script writes the table Knut asked for (Name, "Include as default
  [yes/no]", Comments, plus the key) and reads it back filled in
  (`--from-table`), so the release list is one command once his users answer.
* **The beta rule** (Knut: *"pre-select 4 presets for each type of paper size
  and instrument, so that the 4 selected are between 1 and 4 pages with
  different patch sizes, but skipping the smallest and the largest presets"*),
  as `core.curated_presets.beta_selection` reads it, per instrument group and
  paper (A3 portrait and landscape are one paper; a photo card in cm and in mm
  is one paper):
  1. more than four presets on that paper: drop the one with the fewest
     patches and the one with the most;
  2. keep those of one to four sheets;
  3. four or fewer left: all of them; more: four bands by patch count, one pick
     per band, preferring a patch width not yet picked, then the band's middle.
  Result for beta 42: **62 of 185** shown (ColorMunki 15, i1Pro 20, i1Pro 3
  Plus 11, CR30 8, Scanner 6, Red River Paper 2).
* **Only the person's own decisions are stored**, in the setting
  `builtin_presets_shown` as `{key: shown}`: a preset is recorded when its box
  differs from the shipped list, and stays recorded once it has been. A preset
  never touched follows whatever a later release ships; a preset touched keeps
  the person's answer. Closing the window without a change stores nothing.
  *(Since C3a: OK without a change stores nothing; Close, Escape and the
  close box never store anything.)*
  *Amended (challenge 3 of beta 42, B8-1033, not confirmed):* only a TRUE
  difference is stored. A preset is recorded exactly while its box differs
  from the shipped list; a box that agrees with it again is forgotten, and
  with nothing left the setting is removed. Ticking the boxes back to the
  shipped list by hand had left all 62 stored as the person's answers, so a
  later release's list would never have reached them. The cost, for Knut to
  weigh: an answer that happens to agree with the shipped list is not kept,
  so a later release that changes that preset moves it too. Whether the
  window should also offer "Restore shipped selection" is his question and
  was not built.
