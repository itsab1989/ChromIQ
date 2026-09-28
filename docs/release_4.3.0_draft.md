# ChromIQ 4.3.0: release notes (DRAFT)

**How this becomes the release, at the stable tag** (rehearse it before the day):

1. Copy `CHANGELOG.md` aside.
2. Remove every `## v4.3.0-beta.N` section (48 of them, including the two that sit between the 4.2.x entries, beta.2 and beta.3). Keep `## v4.2.7` and everything older.
3. Paste the `## v4.3.0` section below under `# Changelog`, above `## v4.2.7`.
4. `python scripts/release_notes.py v4.3.0` must render every section (New, Changed, Fixed, Known issues), and `tests/test_release_notes.py` must pass with `APP_VERSION = "4.3.0"`.
5. Re-count before publishing: presets on the site (`docs/index.html`, 187 today), languages (`data/i18n/*.json` plus English, 14 today). Never publish a number nobody re-counted.
6. The stable tag needs Basti's explicit go.

Written for someone updating from 4.2.7. Anything a beta added and later took back is left out; where a beta entry was changed later, the final behaviour is described.

---

## v4.3.0

**The Measurement Report grows up.** ChromIQ 4.3.0 turns the report into six report types judged against named limit sets, including the published ISO 12647-7 and ISO 12647-8 values, adds evenness across the sheet and repeatability, and keeps every report as a dated document you can reopen exactly as it was saved. Create Chart gets a curated list of 187 ready-made presets, a finer layout engine and clearer sheet text, and ChromIQ is now complete in 14 languages.

### New

- **Six report types.** A pulldown above "Judged against" chooses what the report is for: **Full colour check** (everything ChromIQ measures), **Colour summary (one page)** to hand over with a job, **Grey and tone check** for the neutral axis and the mid-tone ramps, **Printing record (not graded)** that records what was printed and measured without judging it, and **Validation print check (ISO 12647-8)** and **Contract proof check (ISO 12647-7)**, judged against that standard's limits.
- **Limit sets.** A limit set is one column of numbers a report is judged against. ChromIQ ships **ChromIQ default**, **ChromIQ tight** and **Quick check**, two **Custom ISO** sets that start from limits researched from industry practice and are yours to change, and the published **ISO 12647-7:2016** and **ISO 12647-8:2021** values as read-only columns. The **Report limits** window (Preferences ▸ Reports) shows them side by side, and every row has an info icon that explains the metric and what you can do about it.
- **The report owns its limit set.** Each report is judged against the set chosen for it, and a report names its type and its limit set at the top. A metric whose limit is "–" is left out of the report entirely, graphs included.
- **Evenness across the sheet.** Two rows judge how even a print is over the page: the largest difference between two of the nine sheet areas, and the largest difference between one area and the whole sheet. The average share of the measurement noise is taken out before the result is compared with the limit, and a row is judged only where the chart has enough patches in each ninth of the page.
- **Repeatability.** Two rows of ChromIQ's own: how far apart repeated patches on one sheet read, and how far apart the same chart reads when it is measured again.
- **Paper and solids against the profile.** On a verification, the paper white and the solid colours are compared with the profile the sheet was printed through, and paper white is the patch printed with no ink.
- **ISO 12647-7 and ISO 12647-8 values ship**, values only, together with eleven bundled Fogra printing conditions, each with its credit. You can give ChromIQ a newer Fogra file yourself; the Reference values window says which copy is in force, set by set. Preferences ▸ Licences names everything ChromIQ ships that somebody else made.
- **A trend graph for every judged group**, titled "Trend over time", with a line for every limit and a description beside each label. A date that was not judged is marked with a red x.
- **Reports across runs and projects.** A report can cover several profile runs or several projects, and projects kept in different folders can share one. Calibration runs make reports too.
- **Saved reports are documents.** "Report shown" lists every saved report, grouped by project and run, and "New report…" starts a fresh one. A saved report opens, and prints to PDF, exactly as it was saved. Nothing on the page changes until you press **Generate report**, which then asks whether to update the report you selected or create a new one; either way the result is worked out by this version.
- **"Before you measure this verification chart"** tells you on the Measure tab which metrics the chart you printed can answer, and **"Which presets can be used for verification?"** does the same for every preset before you print. Presets made for verification are marked ●.
- **A curated preset list.** The gear in Create Chart ▸ Manual ▸ Presets opens **Settings for built-in presets**: tick the presets you want to see directly, and the rest wait under "▸ N more presets". The list can be exported and imported as a file, and can be filtered by the paper chosen in Create Chart (off by default).
- **New built-in presets from Knut**, among them seventeen charts for the two photo-card sheets, eight 7.5 mm i1Pro "Maximised - No Clip-border" charts, six straight-strip CR30 charts, and nine "by Pharmacist" charts with a full page layout.
- **i1Profiler measurements for profiling runs.** A profiling run can import an i1Profiler measurement on the Measure tab, as a verification already could.
- **"Save measurement report"** is on the Measure tab, and **Preferences ▸ Reports** holds the Measurement Report's defaults.
- **Text on all four edges of the sheet**, with an Alignment box for the line along the bottom, font sizes in half points, and the ChromIQ branding placed at the end of the clip border.
- **Help windows show their headings and lead-ins in bold**, in every language.
- **Ukrainian**, contributed by LackiUA on issue #198, makes ChromIQ fourteen languages.
- **A demo package**, `ChromIQ-Demo-Projects_v4.3.0.zip`, is attached to the release: projects that show every report type, every limit set and every metric, to try without an instrument.

### Changed

- **Every row reads PASS or FAIL**, a row the chart cannot answer reads N-A with a note saying what the measured chart lacks, and a sheet the report does not judge reads INFO. A metric that does not apply never counts against your result. The two Pass-threshold boxes of earlier versions are gone.
- **A profiling measurement is no longer graded**: its own chart built its profile, so the report records it instead.
- **One name per metric everywhere**, the same in the report, its graphs and the Report limits window, with the unit.
- **Report text is written for the person the report is handed to.** It speaks about the measured chart, not about ChromIQ's windows.
- **Where a report lives.** A report of one measurement stays in that date's folder, a report of several dates of one run with that run, a report across runs with its project, and a report across projects in the ChromIQ folder. Reports already on disk stay where they are.
- **The layout engine's two modes are cleaner.** In "Prioritise chart area, then fit patches to it" the columns and rows, the minimum patch width and the margins decide the chart; a patch size, patch scale or chart offset typed for "Prioritise patch size" no longer takes over.
- **With the CR30**, "Use the ChromIQ layout engine instead of printtarg" is ticked and locked, because the CR30 is always laid out by the engine.
- **Save as Defaults** brings a session back as it was saved, for every instrument and paper.
- **A found calibration file** is offered where the layout that is in use reads it: in the layout section's "Printer calibration" with the ChromIQ layout engine, in printtarg's own fields otherwise.
- **The main button of a window** is filled in that window's colour, and a destructive action is never the default. Selected rows take the colour of their tab.
- **The paper lists** name the orientation in your language.
- **No text says "drift"**; ChromIQ says "change".

### Fixed

- **Build Profile no longer empties the profile it replaces.** A second build on a run that already had a profile left a zero-byte file and no copy; the previous profile is now kept in the run's "old" folder.
- **A report could be judged against several sets of limits at once**, could drop measurements without saying so, or store measurements you had not ticked. A report now holds exactly the measurements and the one limit set it was made with.
- **Save report as PDF writes the page on screen**, also after a setting was changed and not yet generated.
- **Renaming a project or deleting a profile run keeps saved reports right.**
- **Keys pressed at a ChromIQ window no longer reach the instrument**, and closing "Wrong Strip Read" with the window's own close button no longer accepts the misread strip: it asks for the strip again.
- **A reopened project builds the chart it was built as**: the automatic patch count, the paper, a built-in preset's patch set and a patch set loaded from a file.
- **Margin readings and warnings describe the sheet you are looking at**: the Margin Inspector, the bottom-text and strip-letter warnings, and the remedies they name, which now point at a control that helps.
- **Honeycomb charts** keep their strip letters, outlines and blanking right with "Show only measured patches".
- **Selecting a scanner preset** no longer takes seconds, **FROM PROFILE GAMUT** no longer freezes the window, and switching Run type to Verification no longer stalls it.
- **Apply Calibration finds the project's calibration.**
- **A rare crash** when memory was cleaned up while a window was still receiving an event.
- **Translations**: every text is in all fourteen languages, each translation read a second time against the English, and labels that were cut off, or ran into each other, in some languages now fit.

### Known issues

- **Do not open a 4.3.0 project in ChromIQ 4.2.7.** 4.2.7 cannot tell that the project is newer, and saving it there drops the report settings this version keeps for its runs. If it has happened, set the run's "Default for this run" again in Edit limits.
- The printed help card for CMY+N charts takes two pages in German, French, Polish and Ukrainian.
