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
> `data/preset_defaults.json`. Tests: `tests/test_curated_builtin_presets.py`,
> `tests/test_k39_preset_list_export_import.py`,
> `tests/test_k41_preset_paper_filter.py` (the paper filter, C7).

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
  **Amended (K42-3, Knut #182 5832746557 and 5833232475, beta 43,
  B8-1144, awaiting confirmation):** the paper filter (C7) applies to
  built-in presets only, and the third paragraph says so: *"Your own presets are not affected: neither the ticks nor the paper filter below changes them, and they always stay at the top. OK keeps your choice; Close leaves the lists as they were."* German by hand (Du-Form): *"Deine eigenen Presets sind nicht betroffen: Weder die Häkchen noch der Papierfilter unten ändern etwas an ihnen, und sie stehen immer oben. OK übernimmt deine Auswahl, Schließen lässt die Listen, wie sie waren."* The window has a help
  icon (ⓘ) beside its paragraphs for the whole feature (ticks, the
  "▸ N more presets" arrows, OK and Close, Export list and Import list,
  the paper filter, own presets); the box has its own, on its right (C7).
  The window's own list is not affected by the box: it always lists every
  built-in preset with its tick.
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

### C6. Export list and Import list (Knut, #182 5831246553, beta 43, B8-1101 to B8-1103)

⏳ **Awaiting confirmation. Confirmed by:** *nobody yet.* Verified by driving
the real app on screen, English and German (proof in
`~/Desktop/ChromIQ-beta43-proof/k39-export-import/`), which proves what the
app does; whether it is what it should do is Knut's or Sebastian's call.

Knut's request: *"one "Export list" and one "Import list". The export button
saves a csv file of the table with the current settings. The import button
imports the same type of file back into the app and updates the checked
settings. file dialogs open in the ChromIQ default folder. The saved filename
should have a pre-defined name that explains what this list is. The import file
dialog is filtered to only accept csv file type, as was exported. Closing the
window then updates what is shown in the pulldown."*

| What | Behaviour |
|---|---|
| Where | two buttons at the bottom LEFT, "Export list" then "Import list"; OK and Close stay the pair at the bottom right (C3a) |
| The window's text | a fourth paragraph: "Export list saves this table as a CSV file, with the ticks as they are now. Import list sets the ticks from such a file. Like any change here, an imported list is kept only by OK; Close discards it." |
| Export | writes the ticks AS SHOWN, unsaved changes included, one row per built-in in the pulldown's order |
| The file | exactly the table `scripts/make_preset_defaults.py --table` writes: columns Group, Name of preset, Include as default [yes/no], Comments, Key; the answer column filled "yes" or "no". UTF-8 with a byte-order mark (so a spreadsheet shows the "·" in the names). Both the window and the script write and read it through `core/curated_presets.py`, so an exported file goes through `--from-table` and a filled-in table comes back through Import list |
| The name offered | "ChromIQ built-in presets shown.csv", the same in every language (the file travels between people) |
| Both file windows | open in the ChromIQ folder (`custom_output_path`, else ~/ChromIQ: the folder projects go in); filtered to "CSV files (*.csv)"; a name typed without ".csv" gets it |
| Import, matching | by the Key column; the columns are found by their header, so their order does not matter; a comma or a semicolon separates them (a spreadsheet in a decimal-comma language saves "CSV" with semicolons); UTF-8 or the Windows code page |
| Import, answers | yes, y, x, 1, ja, true tick; no, n, nein, nei, 0, false clear; any case |
| Import, reported and skipped | a key this ChromIQ does not have; a row with no key; an empty answer; an answer that is neither yes nor no. The last two leave that preset's tick as it was |
| Import, not named | a built-in the file does not name keeps its tick |
| Not a table | a file without the Key or the answer column: "This file is not a list of built-in presets. Nothing was changed." A file that cannot be read as a table at all (a cell over 128 KB, or a binary file) says the same, with "It cannot be read as a table: a cell is too long, or it is not a text file." (B8-1162) |
| A key listed twice | the last line that answers it counts, and the summary says so: "Lines {lines}: {name} is listed more than once. The last of them counts, so it is ticked." (or "unticked") (B8-1163) |
| The summary | a message after every import: "The window now shows the ticks from the list." then Ticked: N, Unticked: M, Skipped: K, and "Not in the file, so left as they were: L" when L > 0; one line per problem with its line number (the first ten; the rest under the details); "Nothing is stored yet: OK keeps these ticks, Close discards them."; its button is "Back to the list", not a second OK |
| A status line | above the buttons, after every export and import, whatever came of it: "Saved the list to {path}.", "The list was not saved to {path}.", "Imported {path}. OK keeps these ticks; Close discards them." or "{path} was not imported. Nothing was changed." (B8-1164) |
| Applying | an import changes only the window. **OK stores it and rebuilds both lists; Close, Escape and the close box discard it**, as every change in the window (C3a). Knut wrote "closing the window then updates"; since B8-1097 the window has OK and Close by Basti's decision, so OK is what applies |
| Comments | a Comments cell read by an import is written back by the next export from the same window |

`scripts/make_preset_defaults.py --from-table` keeps its own, looser reading
of an answer (anything but a yes is "not ticked", an empty cell included),
because it builds the shipped list from a blank table, where an empty cell
means "not chosen". The window reports those cells instead, because there a
tick already means something.

### C7. The paper filter (Knut, #182 5832303551 and 5832436639, beta 43, B8-1131 to B8-1134)

⏳ **Awaiting confirmation. Confirmed by:** *nobody yet.* Verified by driving
the real app on screen, English and German (proof in
`~/Desktop/ChromIQ-beta43-proof/k41-paper-filter/`), which proves what the app
does; whether it is what it should do is Knut's or Sebastian's call.

Knut's request: *"Add a checkbox in the window named "Filter preset-dropdown
list according to selected paper size". When OFF, all presets are listed in
the dropdown lists for "Select preset" and the "built-in presets" button,
according to what is selected to be shown in the settings window. When ON,
the dropdown lists for "Select preset" and the "built-in presets" button show
only the presets related to the selection in "Paper" field in Create Chart
(either "Paper size" in Guided or "Paper" in Manual mode), and according to
what is selected to be shown in the settings window. The presets under
headings Scanner are always shown. The Red River Paper presets area also
filtered, as the presets are specific for a Paper size. If the Paper size
setting is Custom, then the the Custom Size fields are specifying the paper
size, but since we do not hold custom size presets for all possible sized,
all the presets using the Custom Paper size setting will be shown in the
dropdown lists for "Select preset" and the "built-in presets" button."* And
(5832436639): on Custom the ticks and the "▸ N more presets" arrows still
apply, exactly as on any other paper.

| What | Behaviour |
|---|---|
| The box | "Filter preset-dropdown list according to selected paper size" (German "Presetliste im Aufklappmenü nach gewählter Papiergröße filtern"), under the list, above the buttons. ~~Its tooltip says what it does~~ **Amended (Knut, 5833232475, B8-1145):** a help icon (ⓘ) on its right says what it does and what it applies to: built-in presets only, both pulldown lists, the paper of Guided or Manual, orientation, Scanner always shown, Custom, and the ticks and arrows still applying within the filtered list |
| Stored | the setting `builtin_presets_paper_filter`, ~~default off~~ **default ON (Knut, 5833232475: *"It should be default ON"*, B8-1145): a person who never touched the box has it on, and a stored off is kept.** **OK stores it, Close, Escape and the close box discard it**, like the ticks (C3a). The box opens as stored |
| The window's own list | **not affected by the box** (Knut, 5833232475): it always lists every built-in preset with its tick, whatever the box and the paper |
| OFF | both lists exactly as before: the ticks and the arrows, nothing else |
| ON: which paper | the Paper field of the mode on screen: Guided's "Paper size", Manual's "Paper" (the gamut module lays out through Manual's). Live: the lists follow a change of paper and a switch between Guided and Manual at once |
| ON: a preset's paper | the printtarg `-p` code it lays its chart out on, the one selecting it puts in Manual's Paper field: a Full-layout-setup preset's own `paper`, a "by Pharmacist" bundle's paper folder. Every built-in has one. *Knut, 5833232475, asked: "Yes"* |
| ON: orientation | part of the paper. Both pulldowns list each orientation as its own entry (A3 Portrait is `A3`, A3 Landscape is `420x297`, A4 Landscape `A4R`), so the match is exact: A3 Portrait lists only portrait A3 presets. *Knut, 5833232475, asked: "Correct"* |
| ON: Custom | Manual's "Custom (enter dimensions)": every preset on a size the Paper field does not name (the 10 × 15 and 13 × 18 cm cards), whatever its dimensions and whatever the Custom boxes hold. Guided has no Custom entry |
| ON: Scanner | always listed in full, whatever the paper |
| ON: Red River Paper | filtered like every other group |
| ON: ticks and arrows | still apply within what is left: per group the ticked presets on that paper, then "▸ N more presets" over the unticked ones on that paper, N counting only those; opening the arrow shows the rest of that paper's presets (Knut, 5833232475: *"Same function as before"*). Custom included (5832436639) |
| ON: an empty group | no heading, no separator, no arrow, in both lists |
| ON: the person's own presets | ~~filtered too, by the paper each stores (Manual's Paper field when it was saved, `printtarg_-p`); one that stores no paper is always listed. They stay at the top~~ **Amended (Knut, 5833232475: *"No. This feature only apply build-in presets"*, B8-1145): never filtered. Every one of them is listed, at the top, whatever the paper; the window's third paragraph and both help icons say so** |
| The selected preset | never changed by the filter. When the paper moves away from it, it stays selected and loaded, and stays listed in its group (with its heading) in "Select preset", so the closed pulldown and the open list show what is loaded; once another preset is chosen, it leaves the list the next time the list opens. The Built-in presets list has no selection and lists only the paper's presets *Knut, 5833490026: "sure, but if a user changes the paper size after a preset is loaded, we must assume the user intends to change the size, so the preset list will change to show presets with the newly selected paper. But the previously selected preset [...] stays loaded and stays visible in the pulldown until you choose another preset." That is what is built; pinned by `tests/test_k42_preset_groups_follow_the_instrument_pulldown.py` (B8-1147)* |
| Every key | stays an entry of "Select preset": a filtered preset is hidden and disabled like one under a closed arrow, never removed, so a stored selection and the "Which presets can be used for verification" double-click still find it |

### C8. The groups come in the Instrument pulldown's order (Knut, #182 5833490026, beta 43, B8-1146)

⏳ **Awaiting confirmation. Confirmed by:** *nobody yet.* Verified by driving
the real app on screen, English and German (proof in
`~/Desktop/ChromIQ-beta43-proof/k42/`).

Knut: *"The sequence of the groups of presets, which are related to specific
instruments, should be placed in the "Select preset" and the "built-in
presets" button in the same sequence as in the dropdown list of the
Instrument field. So, "Colormunki / i1Studio..." heading with its presets
should not come first, but third. "i1Pro / i1Pro 2 ..." heading with its
presets come first, etc. Scanner and Red River Paper always come at the end
like before."*

| What | Behaviour |
|---|---|
| The order | i1Pro / i1Pro 2 / i1Pro 3, i1Pro 3 Plus, ColorMunki / i1Studio / ColorChecker Studio, CR30 (ChnSpec), then Scanner, then Red River Paper. The person's own presets stay on top, with no heading |
| Where it comes from | the Instrument pulldown's own source, `INSTRUMENT_LABELS` in `data/patch_db.py` (what Guided's Instrument field lists, in its order); Manual's Instrument field (`printtarg -i` in `data/parameters.yaml`) lists the same codes in the same order, and a test holds the two together. No second list: `instrument_group_rank` in `ui/tabs/tab_chart.py` ranks each group by its instrument's place there, and a group that is not an instrument goes last, keeping its place |
| Every list | sorted once, in the registry `BUILTIN_PRESET_GROUPS`, so every list follows: "Select preset", the Built-in presets list, the gear window's list and its Export list CSV, "Compare with profile", "Which presets can be used for verification?" (its "Preset pulldown order" keeps the groups in this order), and `scripts/make_preset_defaults.py --table`. `data/preset_defaults.json` was rewritten in the new order; it ticks the same 62 presets |
