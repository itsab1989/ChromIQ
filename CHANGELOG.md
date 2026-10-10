# Changelog

## v4.3.3-beta.18 (unreleased)

### Fixed

- **Read single patches: the reader named beside "Detect automatically" follows the instrument you plug in or pull out while the window is open.** It could keep naming the reader it found when the window opened (Start always used the right one). Every 2 seconds the window now asks the operating system whether its list of USB devices has changed, inside ChromIQ, which costs well under a millisecond and opens nothing; only when something was plugged in or pulled out does it work out the reader again. It does not look while a session is running or while the window is closed.
- **Button text that changes no longer gets cut off.** "Undo auto align" in the scanner window (it read "NDO AUTO ALIG" when the window was at its narrowest), the scanner window's build button after switching between a printer profile and a scanner or camera profile (eight languages), "Install Profile Anyway" in the scanner window (Russian), "Hide each set's credit" in Preferences (Swedish) and "Continue Measurement" on the Measure tab (Russian). Each of these buttons now keeps room for all of its texts. The scanner window can get slightly wider in Russian and Ukrainian as a result. In Russian and Ukrainian, "Continue Measurement" now reads "Продолжить", as "Continue" does elsewhere in the app: the full wording made the Measure tab's buttons run into each other and past the edge of the panel (Russian), or left them no room to spare (Ukrainian).

## v4.3.3-beta.17

### New

- **Read single patches: delete single readings.** Select one or more readings and press Backspace or Delete (while the list has the focus), click the new Delete button, or right-click a reading and choose Delete. "Undo delete" (the same button, or Cmd+Z in the list) puts them back where they were until the next reading. The other readings keep their names, a deleted number is never given out again, Save writes exactly what the list holds, and closing asks again after a delete while readings are left.
- **The CR30 says which unit and which firmware it is, in the log** (Basti, 2026-10-09). At every connect ChromIQ logs the model, serial, internal id, software and hardware version: over USB from the identity question it already asked, over Bluetooth from the instrument's own read-only device-info question, asked once per connection and given up after 5 seconds without ever holding up a measurement. A software version other than the tested V11.3.0.0.20231219 is marked in the log. Nothing is shown on screen. The last connected unit's details head the CR30 Bluetooth report (Tools ▸ Instruments).
- **ChromIQ can be installed with Homebrew on a Mac, together with ArgyllCMS, in one command.** Use `brew install --cask itsab1989/chromiq/chromiq` for the stable version, or `brew install --cask itsab1989/chromiq/chromiq@beta` for the newest beta. ChromIQ then opens straight away: the cask removes the macOS download quarantine, so there is no "could not verify" warning and no right-click and Open. `brew upgrade --cask chromiq` keeps it up to date, and each release updates the casks automatically. You need [Homebrew](https://brew.sh) itself first. The DMG downloads work as before. From this release on, each release also lists two Mac files ending in `_homebrew.dmg`. They are identical copies that Homebrew downloads, so Homebrew installs can be counted separately. If you download by hand, take the normal DMG, the one without `_homebrew` in its name.

### Fixed

- **A CR30 taught over Bluetooth could not be found by the next session** (Basti, beta 16). Closing Read single patches while the calibration was still connecting let go of the instrument, but the teach-in window then opened a new Bluetooth link on the closed connection, and nothing ever closed it; a CR30 that is still connected stops advertising. A closed connection can no longer open the instrument again, a link that arrives after the window closed is let go at once, the calibration ends when its window has let go, closing from the window really disconnects (it failed on a busy event loop before), and quitting ChromIQ lets go of the instrument.
- **Stop did nothing while the CR30 had switched itself off, and switching it on again did nothing until the window was closed** (Basti, beta 16). The Bluetooth link is now watched: when it drops, the session pauses, keeps every reading and asks "Your CR30 is not answering" with Reconnect and Stop session. Reconnect finds the instrument again and says Ready only once it is connected. Stop ends the session at once and lets go of the instrument, whatever the link is doing.
- **One Bluetooth reading arriving later than the others** (Basti, beta 16): his log recorded no timing, so the cause could not be read from it. Every Bluetooth reading now logs how long it took after the instrument signalled the press, and a reading the instrument was not ready with yet says so, so the next slow one names its cause.
- **A CR30 press made right after Read single patches says Ready could be lost over Bluetooth** (Basti, beta 16). The window said Ready a moment before ChromIQ was listening, and every read threw away the presses the instrument had announced so far, so a press within about a second of Ready, or across the window's 30-second refresh, was dropped without a word. Old presses are now cleared once, before Ready appears, and never afterwards. A press made before Ready (while "Calibration Complete" is still open) is still not used, and the window's notes now say so: "One reading was taken before this window was ready for it, so it was not used. Take the reading again." USB was never affected.
- **Read single patches looks as it should after Basti's hand test of beta 17.** The "Undo delete" text fits its button in every language; the selected reading and the right-click menu use the window's green instead of the system blue, and a selected reading keeps its own colour swatch, framed; the hex code on a swatch is white on dark colours and black on light ones; a divider between the list and the notes lets you make the notes smaller, and the notes keep following new lines after it is moved; the window opens taller, so eight readings fit; and where the buttons are wider than the screen (French on a 1280-pixel screen) Save and Close move to a second row.
- **"Connected to your CR30 over Bluetooth." is said once**, not twice, in Read single patches, and it is said again after Reconnect, for the new connection.
- **The learned white-tile value is filed under the serial the instrument states itself** (over USB and Bluetooth alike) instead of the Bluetooth name. On every unit we know of the name is the serial, so nothing has to be taught again; a value kept under the Bluetooth address or under a different name moves to the serial the next time the instrument connects over that link.

### Changed

- **The neighbour check is Knut's four steps, and it runs on every kind of chart** (#182, Knut 6071673457, 6078174421, 6082015002, 6085694445). For each of the 2 to 4 read patches nearest in expected colour (within the colour-neighbour radius, from any strip, its own included), its error is the ΔE*ab between its reading and its expected colour; a patch is outlined red when its own error is more than the neighbour limit above the median of theirs. That is the very number every patch card shows. The old first test ("buffer": the readings further apart than the expected colours) is gone, and there is no hidden threshold. It now judges verification charts (through the profile and From Profile Gamut) and calibration charts too, with outlines, and it is checked again after each strip is read (patch by patch: after each patch) and when a measurement is opened. Only a patch's own re-read turns it yellow; a green patch turns red again when a later reading of it is a misread. On the real profiling sheets measured with an instrument (Knut's HP laser and two of his runs, an Epson P300: 3,840 patches) 2 patches are red at the default limit 10 (beta 16: 6). On a sheet read through a scanner, whose readings lie a median ΔE*ab 58 from the expected colours, 16 of 315 are red (beta 16: none): with errors that large, patches close in colour differ from each other by more than 10. Neighbours from the same strip change neither number much; the new rule does.
- **Every threshold of the misread tests is visible and can be changed, per chart type, in one table in Preferences ▸ Measurement** (Knut's layout, approved in 6084176226). The columns are Profiling charts with estimated colours, Profiling charts made with a pre-conditioning profile, Verification charts and Calibration charts; the rows are the Patch error limit (95 / 20 / 5 / 95), the Strip test (on / on / off / on), the Neighbour check with its switch, its Neighbour limit (10 / 5 / 3 / 10) and its Colour-neighbour radius (15 / 30 / 30 / 30), and the Same-reading tolerance (3, one value for every chart type). All values are ΔE*ab. Each name carries a one-sentence tooltip, and each test has its own help: what it does, its values by chart type, what it needs, when it runs, the patch colours, and tips (a neighbour limit of 7 to 15 on verification charts for a laser printer).
- **Verification charts: patch error limit 5 instead of 10, and the strip test has its own box, off by default** (Knut 6070058549, 6084176226). Its help explains what the strip test does on a verification chart, measured on four laser verification sheets: about half the red patches on a clean laser sheet, at the cost of some small or partial misreads.
- **Your settings come with you** (settings schema 29, run only for settings older than it). A verification limit still at the old default 10 becomes 5; any other value you set is kept. A strip test you had switched off stays off on profiling and calibration charts. A changed neighbour "buffer" becomes the neighbour limit of the same chart type. A changed limit for charts with estimated colours is also given to calibration charts, which used it until now.
- **The patch cards speak Knut's words** (approved in 6078174421 and 6084176226): "This patch is ΔE 6.2 further from (or closer to) its expected colour than the 4 patches nearest in colour (median)." on every card, "has equal distance" at 0.0; a red card says "Red outline: ΔE 13.2 further from its expected colour than the 4 patches nearest in colour (median), passing the neighbour limit (10.0). Probably a misread: read it again."; the patch error limit is named with its value and its chart type ("reached the patch error limit (20.0, profiling charts made with a pre-conditioning profile), and it stands out from its strip (strip test)"). No card says "buffer" or "read in other strips" any more, topics are separated by an empty line, and every card ends with "Checked again after each strip is read: …" (patch by patch "… after each patch is read") and "See Preferences ▸ Measurement for threshold values."
- **"Which presets can be used for verification?" names its counts** (Knut 6078432080, 6085694445). The line under the list reads "Answering every metric asked, own colours: n" beside the From Profile Gamut count; the column headings' tooltip begins with what the columns count, and a help icon explains own colours (printed through the profile for a verification, printed raw for profiling) and From Profile Gamut (verification only).
- **The Print Chart help says what a Canon does on plain paper** (approved by Basti, 2026-10-09): the driver always uses its own colour processing there, whatever program prints, and ChromIQ prints the chart the same way, so the profile fits prints from Photoshop, Preview and other programs as long as Plain Paper and the same print quality are chosen there.

- **Italian, Norwegian, Polish, Russian, Swedish and Ukrainian: the new misread texts call a chart what the rest of ChromIQ calls it** (review of beta 17). The chart-type columns of Preferences ▸ Measurement, their help, the patch cards and the presets window had brought in a second word ("target", "testark", "wzornik", "шкала") beside the one Create Chart and Print Chart use ("grafico", "kart", "wzorzec", "мишень", "diagram", "діаграма"). Ukrainian now says "понад межу" (more than the limit) instead of "понад межею" (above it).
- **VoiceOver names every number box of the misread table** (its parameter and its chart type); it read out a bare value before.

### Documentation

- **The README and the website explain the Homebrew installation**: installing the stable version or the beta, switching between them, updating, uninstalling (your projects in `~/ChromIQ` are always kept), and what to do when ChromIQ is already in your Applications folder.

## v4.3.3-beta.16

**More printers print the chart in the state your photos print in (now measured on 27 Canon, Epson and DNP models), at the resolution and quality their own print dialog uses; the Print Chart tab offers the quality your photos use; ChromIQ's own printing sends the chart at exactly 100 %; and two measuring glitches are fixed (the next-strip arrows after paging back, and the preview's switch staying open). If a setting changed back by itself after an earlier update, set it again once: it now stays.**

### Fixed

- **Canon PIXMA PRO-10S, iP8750 (iP8700 series) and iX6850 (iX6800 series) were unknown models on the direct route, and the PRO-100's table was a hand measurement** (vendor tests round 2, 2026-10-09). These Canon drivers (16.9x) keep their media database as a binary table that beta 15 could not read, so the direct route stopped with "ChromIQ does not know this printer's paper profiles yet". ChromIQ now reads that table: the paper profile of every paper type at every quality, the qualities each paper type allows, and the quality the Canon dialog picks. It reproduces all 29 paper types measured on the PRO-100's dialog and every paper type measured on the PRO-10S, iP8700 and iX6800 dialogs. On these models the paper profile depends on the quality (Photo Paper Pro Luster is "LU1" at Fine, "LU3" at Normal), and the chart now carries the profile of the quality it prints at.
- **Canon imagePROGRAF PRO-2100, PRO-4100 and PRO-2600** print at the quality their dialog picks for the paper (its own default, for example Photo Paper Pro Luster at the 4th position); the rule ChromIQ used for the PIXMA dialogs (their "Standard" position) gave the next better one.
- **A Canon on Baryta, fine-art or heavyweight paper is fed from the manual feed**, as the Canon dialog does for those papers; the direct route sent nothing and the driver kept the top feed. Read from the driver's media database (102 paper types measured on five models agree), and measured on the PRO-10S, whose binary table does not say.
- **Epson: the direct route sends what the Epson dialog writes for the paper, on every model whose driver is installed.** ChromIQ now works the dialog's values out from the driver's own data the way the dialog does: the colour mode for application colour matching (for example the XP-15000 got "EPSON Vivid" off only on plain paper), the quality, the black ink of the SC-P6000 to P9000 (Matte Black on matte papers) and their paper configuration (thickness, platen gap, suction, roll tension). Checked against every Epson dialog measured in both vendor rounds (25 models). Through the Epson driver's own filter, printed to a capture queue, the black ink and the paper configuration change the commands the printer receives; with them the direct route's stream equals the dialog's.
- **The chart is rasterised at the resolution the printer's own dialog sets for the paper** (Canon and Epson). Both dialogs set the driver's Resolution option per paper type and quality (Epson Premium Glossy 720 dpi where the driver's standard is 360 dpi; Canon PRO-10S 600 or 1200 dpi, imagePROGRAF 300 or 600 dpi), which the direct route never sent. Printed through the Epson driver's own filter to a capture queue, an ET-8550 chart on photo paper then reached the printer in different commands and raster data than the same chart through the dialog; with the dialog's resolution the two are byte for byte the same (also on the SC-P900, SC-P600, SC-P6000, Stylus Pro 3880 and PictureMate PM-400). Canon: 91 of 91 dialog measurements give the same resolution.
- **The Stylus Photo 1390 and 1400 dialogs stay in automatic mode.** The direct route switched them to the custom mode and the driver's standard quality; it now sends the dialog's automatic settings and its quality for the paper. The SC-P900, SC-P700 and SC-P5300 also get the quality their dialog picks (beta 15 sent none).
- **Epson Stylus Photo R2400, R2880, 2200 and SC-P7000/P9000** keep their tables in one folder per ink set, which beta 15 did not look into; they were unknown models.
- **Epson PictureMate PM-400 and PM-520** have no paper profiles and no way to switch the driver's colour off. Their dialog, in application colour matching, sets the custom mode, the paper's quality and the driver's own colour mode (EPSON Vivid on photo papers); the direct route left the driver's automatic mode. It now sends what the dialog sends.

- **DNP dye-sublimation printers (DS620, DS820, QW410, DS-RX1, DS40, DS80) printed the chart with changed colours on the direct route.** They refuse ChromIQ's PostScript, and the fallback sent the chart as a plain image, which macOS converted into the printer's own profile (white 255,255,255 arrived as 235,240,235; measured on all six: none of 21 test colours unchanged). Their driver has no colour setting at all; their print dialog, in application colour matching, tags the job with that same profile, and every colour arrives unchanged. The direct route now does the same: the chart goes tagged with the printer's profile for the media class (for example "DS620(PD)_Natural"), with no other driver setting.
- **A quality chosen in the Print Chart tab on an Epson printed at the resolution of another quality** (beta-16 review). The Epson dialog sets the Resolution from the paper AND the quality (ET-8550 plain paper: Economy 180 dpi, Normal 360 dpi, Fine and Best Quality 720 dpi); the direct route sent the resolution of the dialog's own quality whatever the new quality row said. Over the installed Epson drivers 623 paper and quality pairs disagreed with the dialog; now none does, PictureMate included. Canon was already right (1,210 pairs checked: profile and resolution follow the chosen quality).
- **A damaged Canon media table, or one a driver update lays out differently, is not read** (beta-16 review). A cut-off table was decoded as far as it went, and papers whose profile record was lost got the default profile as if the driver said so; a short one raised an error out of the reader. A table that does not end inside its file, or that names a profile the PPD does not offer, is now left unread and the model is handled as one ChromIQ does not know, honestly. Checked on about 1,700 damaged copies of the four 16.9x tables (cut, overwritten, swapped between models): none crashed, and no cut-off table changed a paper's profile.
- **A chart larger than the paper is no longer shrunk onto it without a word** (beta-16 review, measured on screen on capture queues). With the paper size left at "Printer Default", or on a printer whose paper size the tab does not offer (PictureMate), nothing compared the chart with the paper: an A4 chart went onto a PM-400's 9 x 13 cm paper shrunk to fit, which moves every patch out from under the instrument. The chart is now compared with the driver's default paper too, and when it would be shrunk the confirmation window, which names the mismatch, shows even when it is switched off. The job itself is unchanged.

- **Epson SC-P7000/P9000: ChromIQ no longer guesses which ink-set edition a queue is** (Basti, 2026-10-09). Their driver ships two editions of the model with different paper profile numbers (Premium Luster 260: 4 in one, 104 in the other; 64 of the P9000's 70 papers differ), and the PPD does not say which one a queue is. The direct route used the first edition in silence. Such a paper is now an unknown one: ChromIQ shows the window for a printer whose paper profiles it does not know yet, the user prints once through the macOS print dialog, which asks the printer, and ChromIQ learns the answer, so later prints go straight to the queue (measured on screen on a capture queue). The same holds for the two Stylus Photo 2200 papers listed under both black inks with different profiles (Archival Matte, Watercolor). The shipped table no longer carries the 54 rows of one edition.
- **PictureMate PM-400 and PM-520: the paper size row knew the size of only two of its eleven papers, and the job always went onto the driver's default 9 x 13 cm page.** Epson names its sizes with codes and the PPD keys their dimensions by PageSize names; ChromIQ now matches the two by the name they share, so a 10 x 15 cm chart on "10 x 15 cm (4 x 6 in)" is compared with that paper and the job carries the matching PageSize too (measured: the page in the job went from 94 x 134 mm, the 9 x 13 cm borderless default, to 102 x 152 mm). A row left at "Printer Default" whose paper does not match the chart is set to the paper that does; a size you chose is never changed, and a chart no paper matches keeps the warning. Labels such as "9 x 13 cm (3<2E>5 x 5 in)" now read "3.5". The same matching applies to every Epson's paper size row.
- **The Canon imagePROGRAF "margin settings of the custom paper size are less than the supported minimum values" alert no longer appears on the macOS print dialog route.** A chart page that is not one of the printer's named papers (5 x 7 in, 4 x 6 in, roll widths, custom sizes) became a custom paper with no margins, which the PRO-2100/4100/2600 driver stops with an alert no program can answer. Such a page on a Canon now gets the driver's minimum margins (the PPD's 3 mm), only when no chart content lies inside them; the chart still prints 1:1 at the same place (measured on capture queues: PRO-2100 and PRO-4100 5 x 7 in, PRO-2600 432 x 600 mm, no alert, content unmoved and uncut).
- **Measure tab: paging through the chart during a measurement no longer loses the "next strip" arrows or leaves the preview's indicator open** (Basti, #182 6079656873, beta 15). Back on the page the reader was on, the arrows were missing until a strip was clicked: every page change dropped them. They now belong to their page and come back with it. And when "Next" reached the last page, the keyboard focus it held went on to the indicator in the preview's corner, which opens for the keyboard, so it stayed open on every page; the other page button now takes that focus. Reproduced and checked on screen with a simulated measurement.
- **Epson direct route: an A3 or A3+ chart is no longer printed shrunk onto the driver's default page, and an A4 chart on "A4" keeps its size** (beta-16 review, measured on ET-8550, SC-P900, R3000 and XP-15000 capture queues against beta 15). Beta 15 sent the Epson paper size without the page size that goes with it, so every chart was laid onto the driver's default page: A3 charts came out at 74 %, A3+ at 64 % (60 % on the R3000, whose default is US Letter). The package's page size fixed that, but a chart filling an A4 page then came out at 97 %, because macOS fits a picture into the page's printable area; such a job now goes as the exact-size PDF, which places it 1:1. A chart on "Printer Default" prints exactly as in beta 15 (the same bytes).
- **An A4 chart on a printer whose default paper is US Letter gets "A4"** (beta-16 review, R3000): the size check forgives 8 %, so the chart counted as matching Letter and went onto it at 95 %. The preselection now prefers a paper of the chart's own size over a default it only matches within that tolerance.
- **The paper size the Print Chart tab picks for a chart no longer resets the media type and quality you had chosen** (beta-16 review, measured on screen): picking "A3" for an A3 chart put Media Type and Print Quality back to "Printer Default", so the job lost its paper profile choice.
- **imagePROGRAF on the macOS dialog route: a chart whose only ink near the edge is printtarg's side line now gets the driver's margins too** (beta-16 review). Every ink pixel counted as chart content, and printtarg's info line runs from edge to edge on a 4 x 6 in chart even with -M6, so such a chart kept no margins and the Canon alert came back. Only solid ink (patches, scan markers) counts now; the driver's 3 mm band may clip that line, never a patch.
- **PictureMate: one "Borderless" row instead of two, and the quality note only while a quality is chosen** (beta-16 review). The PPD's own Borderless switch is now set by the row every Epson has; at "Printer Default" the note named a quality that was not there.
- **A settings update no longer resets choices made since the previous one** (beta 16 final). Every new settings schema re-ran all earlier one-time steps, so a value a user had chosen after its step was taken for an old default: the bump for the PDF default would have switched "Restore last active tab" off, ArgyllCMS chart reading back to ChromIQ's engine, report saving back on, the printtarg layout back to ChromIQ's engine, and a chosen 30 for the profile-made-chart limit back to 20. Each step now runs only for settings older than it. The earlier settings updates did the same, beta 15's among them: if one of these settings changed back by itself after an update, set it again in Preferences once; it now stays.
- **A landscape chart sent as the exact-size PDF came out unturned and cut off** (beta 16 final, measured on PRO-300, ET-8550, Gutenprint HP and HP DeskJet capture queues). The PDF's page took the chart's orientation, and macOS never turns a landscape PDF page onto portrait paper: the middle of the chart landed on the sheet and the rest was lost. This hit every Epson job with a paper size since the beta-16 review, and every landscape chart once the PDF became the default. The page now keeps the paper's orientation and the chart is turned onto it, still at 100 % (the TIFF route always turned it).
- **On a Canon with the paper size at "Printer Default", the exact-size PDF printed borderless at 101.7 %** (beta 16 final, PRO-300 capture queue). The job named no paper, and macOS matched the PDF to the driver's borderless A4. The job now names the driver's default paper when it is the chart's size (A4 on the PRO-300), and the chart prints at 100 % with the normal margins.
- **The "Possible paper mismatch" warning and four status lines of the Print Chart tab were always in English.** They are translated into all 13 languages; the warning lost its em dash.

### Changed

- **ChromIQ's own printing sends the chart as the exact-size PDF by default** (Basti, 2026-10-09). This only matters while "Use default macOS printer dialog" is off; the macOS print dialog stays the default way of printing and never uses it. Where macOS refuses PostScript (and on every Canon or Epson), the chart went as a TIFF that macOS shrinks into the printable area: measured on capture queues, 98.5 % on a PRO-300 at "Printer Default", 96.8 % on "A4", 94 % on a PictureMate 4 x 6 in, 91.5 % on an HP DeskJet. The PDF prints at 100 % with the same colours (pixel-identical on the PRO-300, ET-8550 and Gutenprint HP rasters). PostScript printers are unchanged (byte-identical jobs). Users upgrading are moved to ON (settings schema 28): the box was OFF by default since it existed and Preferences writes every setting on OK, so a stored OFF cannot be told from the old default. Anyone who wants the TIFF unticks it again, and that choice is kept. The box's help now says where it applies, that ON is the default, and what OFF really shrinks.
- **The Print Chart tab has a quality row for Canon, and it offers the highest quality** (Basti, 2026-10-09). It lists the qualities the driver's own dialog allows for the chosen paper type, marks the highest and the dialog's standard, and preselects the quality of your last print on that paper through the macOS print dialog, otherwise the standard. A note under the row says to print your photos at the same quality. Epson models get the same row, read from the driver.
- **The quality row's texts (M-PRINT-QUALITY) are approved** (Sebastian, 2026-10-09), and the Print Chart help now says what the row does: on a Canon or Epson it lists the qualities the driver allows for the paper and preselects the one last used in the print dialog for it, otherwise the driver's standard.
- New models with tables: Canon PIXMA iP8750, iX6850, PRO-10S, imagePROGRAF PRO-2100, PRO-4100, PRO-2600; Epson XP-8700, XP-15000, XP-970, XP-8600, SC-P400, SC-P600, SC-P6000 to P9000, Stylus Photo 1400, 1390, R1900, R2880, R2400, R1800, 2200, Stylus Pro 3880 and 3800, L1800, L800, L805, L810, L850.

## v4.3.3-beta.15

**Charts print in the state your photos print in: on a Canon or Epson, ChromIQ now sends the chart the way Photoshop sends an image when Photoshop manages colours, and macOS no longer converts the chart's colours on the way (measured on 14 Canon and Epson models). Also: the neighbour check judges with 2 neighbours and only marks the patch that is off, with its own switch and two buffers; a failed Profile accuracy table fails a verification; perceptual and saturation verifications are judged on profile accuracy; Guided charts carry no stamp; the Verification box opens on the latest date; every patch card compares the patch with its neighbours; presets are counted From Profile Gamut too; and the preview's switch waits before it closes.**

### Fixed

- **macOS 27 changed every patch of a chart printed through the macOS print dialog** (phase 1 of the Canon investigation, 2026-10-08). The dialog route handed the chart over as "device RGB"; macOS 27 treats that as sRGB and converts it into the paper profile of the medium chosen in the dialog before the printer driver sees it. Measured with the same 23-colour test chart: on Canon Photo Paper Pro Platinum 22 of 23 colours changed (blue 0,0,255 reached the Canon as 25,54,254), on Epson Premium Glossy and Epson plain paper 21 of 23; only Canon plain paper came through unchanged. ChromIQ now reads the profile macOS will convert into, once the dialog has closed, and attaches exactly that profile to the chart, so the conversion changes nothing: 23 of 23 test colours reach the driver unchanged on both printers, photo paper and plain paper, and all 89 colours of a real one-page chart printed from the Print Chart tab. This is what ColorSync Utility's "Print as color target" does.
- **A Canon on photo paper ran its own colour processing on the direct route** (no dialog). ChromIQ said "Colour management: Off (forced)", but the job named no paper profile, and in that case the Canon driver tells the printer to apply Canon's own colour processing. The job now carries the medium's paper profile exactly as the Canon print dialog sets it (Photo Paper Pro Platinum 3, Matte Photo Paper 6, Baryta 10, and so on), and the chart is tagged with that same profile so macOS leaves it alone. On photo and fine art papers the printer's own processing is now off, as for a photo printed from Photoshop; on plain paper, cards and discs it stays on, because that is what a Photoshop print gets there too.
- **The "verified" colour check could not fail.** The dialog route compared its own settings with themselves. After every print, on both routes, ChromIQ now reads the job back from the printing system and says what it really carries in the Print Chart tab's status line ("Sent as job 96. The printing system confirms it carries application colour matching and the paper profile CN_PRO-300_G1_MattePhotoPaper-P.icc."). If the job differs from what ChromIQ sent, a window says which setting differs and that the sheet may not carry the chart's own colours.

### Changed

- **Preferences ▸ Measurement explains every neighbour-check control on hover** (beta 15 text pass). The neighbour check's checkbox shows its full help, as the strip test's does, and both buffer fields (label and box) say what the buffer is, which chart it is for and its default. Texts that had become untrue or incomplete were corrected: the hover card calls the value "your buffer", not "your limit"; the neighbour check's help says the card still compares on a verification or calibration chart; the Measure tab's help on red outlines names the neighbour check; the Verification box's tooltip says it opens on the latest date; the Print Chart help says a Canon keeps its own colour processing on plain paper, cards and printable discs, and that a Canon (and usually an Epson at Printer Default) prints at the quality its own dialog picks for the paper type; the printer tooltip names the exact-size PDF fallback for other printers.
- **A tooltip reused while it is shown is fitted to its new text.** Pointing straight from a long tooltip to another widget, the box kept the long one's size (measured: 460 x 565 px around four lines).
- **A Canon or Epson job carries what a Photoshop print carries, and nothing more** (Basti, 2026-10-08). Photoshop with "Photoshop manages colours" puts one key on a job (application colour matching); the printer's own print dialog adds the medium and its paper profile. ChromIQ no longer adds Canon's "No Color Correction", Epson's colour settings lock, ColorSync=None or the raster format hints to these printers' jobs. On the Canon they changed nothing the printer receives (measured byte for byte); on the Epson the direct route now sends the same colour settings the Epson print dialog writes for application colour matching (Off, No Color Adjustment). Other printers (HP and the rest) are sent the same job options as in beta 14; measured on a generic HP DeskJet queue and on a driverless (IPP Everywhere) queue, the data reaching the printer is byte-identical to beta 14's on both routes. The one difference for them: after a print, the status line now says what the printing system holds for the job. Linux and Windows print exactly as in beta 14 (the new job and the read-back are macOS only).
- **What "as Photoshop" means here** is the printer's settings, not Photoshop's image path. In a hand test (2026-10-08) macOS converted a Photoshop print to the Canon a second time, from the printer profile chosen in Photoshop into Canon's own paper profile, because the Canon driver makes its own paper profile the job's output profile; the Epson print was not converted again, because there the output profile is the one Photoshop chose. ChromIQ does not copy that conversion onto a chart: the chart reaches the driver with its own numbers.
- **The confirmation window says what the job will carry.** For a Canon or Epson, "Colour management" now reads "By ChromIQ, as when Photoshop manages colours", with the paper profile the job selects, and for a Canon whether the printer's own colour processing is off for that paper.
- The direct route sends a Canon or Epson an RGB chart as a TIFF (or the exact-size PDF, when that option is on in Preferences) with the paper profile attached, instead of first trying PostScript, which these drivers refuse.

- **The direct route now knows the paper profile of every medium on 14 Canon and Epson models, and learns any other model** (vendor tests and builder round, 2026-10-08). ChromIQ used to guess a medium's paper profile from its name, which matched what the printer's own print dialog chooses only on the PRO-300/310 and ET-8550/18100: measured on the real dialogs of 13 models, the guess was right for 31 of 76 media. A PRO-1000, PRO-1100 or PRO-200S on photo paper then still ran Canon's own colour processing, a PRO-100 printed with the wrong profile, and every Epson SC-P and Stylus Photo model got no paper profile at all. ChromIQ now reads the table the dialog itself reads, from the installed driver (Canon: the model's media database; Epson: the driver's own condition table), and ships the tables measured for the PRO-300, PRO-310, PRO-200S, PRO-1000, PRO-1100 and PRO-100 (whose table is not readable, so all 29 of its media were measured on its dialog) and the ET-8550, ET-18100, SC-P700, SC-P900, SC-P5300, SC-P800, Stylus Photo R2000 and R3000: 76 of 76 measured media now get the dialog's profile. The Epson colour settings are the ones each model's dialog writes, and never a value the printer's driver does not offer (the SC-P900 was sent a colour mode its driver does not have).
- **A model ChromIQ does not know is no longer guessed silently.** After a print through the macOS print dialog ChromIQ remembers, per printer model, paper type and quality, the paper profile the dialog chose, and the direct route then uses it for that paper type. Until then the Print Chart tab says before printing that it does not know which paper profile this printer's driver uses for the paper type, and offers to print this chart through the macOS print dialog (with the printer already chosen), to print anyway with the driver's standard setting for the paper profile, or to cancel. Printers with no paper profiles at all (generic, driverless, Xerox, Gutenprint) print exactly as in beta 14.
- **The read-back no longer holds up the window.** It runs in the background and gives up after ten seconds, saying the job could not be read back; the chart's profile is compared with the job's byte for byte, not by its name. When the only problem is that the chart could not be given the job's paper profile, the window now says exactly that.
- **The help texts say what ChromIQ really does.** The Print Chart tab's help, the warning under the print buttons, the printer tooltip and the two print options in Preferences no longer say that colour management is "disabled automatically, bypassing ColorSync" or that you must switch colour management off in the dialog by hand. They describe the two routes: the macOS dialog works with any printer (where the driver has paper profiles, its own dialog chooses one); the direct route knows the listed models or learns them, one paper type at a time; on plain paper a Canon keeps its own colour processing, as for prints from Photoshop. The confirmation window's rows (Orientation, Media size, Duplex and the rest) are now translated.

- **The direct route prints at the quality the printer's own dialog picks for the paper** (review 2, 2026-10-08). The print quality is part of the printer state a profile describes. The Print Chart tab has no quality control for a Canon, and ChromIQ sent none, so the driver's standard quality was used: on a PRO-1000 that printed Canvas, the fine-art papers, Photo Paper Plus Glossy II and Semi-gloss at another quality than the Canon dialog does. ChromIQ now reads the quality the dialog picks for each paper from the model's media database; it agreed with the dialog on all 120 Canon media measured on the real dialogs of the PRO-300, PRO-310, PRO-200S, PRO-1000 and PRO-1100. On an Epson whose quality is left at "Printer Default", the job now carries the quality the Epson dialog sets for the paper, read from the driver's own table (13 of 13 measured; for example "Quality" on Premium Glossy instead of the driver's standard "Normal"); a quality you choose in the tab is sent as before.
- Review 2 also: a damaged or hand-edited file of learned paper profiles no longer stops a print; a learned profile is only used while the installed driver still gives that number the same name (a driver update can renumber them); the file no longer keeps the queue's name. Several prints whose read-back each needs a window now show those windows one after another instead of stacked. After "Print Anyway" on a model ChromIQ does not know, the confirmation window no longer claims the printer's own colour processing is "as for prints from Photoshop".
- Review fixes before release: an Epson job on "Photo Paper Glossy" now selects the "Photo Glossy" paper profile, as the Epson print dialog does (it sent "None" on the direct route, and the dialog route showed a false "The print job is not what ChromIQ sent" window although every colour arrived unchanged). The read-back judges a job by the paper profile it really carries, and no longer reports an option sent as "true" or "false" as changed (CUPS stores those as a yes/no value). On a printer whose driver names colour profiles but whose profile ChromIQ could not read after the dialog, the status line no longer implies the chart was protected.

**Do I need to make my profiles again?** Measured on Basti's Epson ET-8550 profile of October (ChromIQ, Premium Glossy): it agrees with his March profile made with ColorSync Utility's "Print as color target" within ΔE00 2.3 on every primary and secondary, where a chart converted by macOS would differ by 8 to 56. That chart was not converted, and the profile does not need to be redone. A profile whose chart was printed through the macOS print dialog on macOS 27 with beta 14 or earlier was converted and should be made again; a Canon profile on photo paper printed on the direct route in beta 14 describes the printer with Canon's own colour processing on, which photos printed from Photoshop on that paper do not get.

### Changed (Knut's items and small fixes)

- **The preview's switch waits before it closes** (Basti). Leaving the small icon in the preview's top right corner no longer closes it at once: it stays open for half a second, and for as long as the pointer stays within a few pixels of it, so the "Paper white" button at its left end can be reached on a natural, curved path. Coming back cancels the close. The opening animation, the keyboard and the placement are as before.
- **A failed Profile accuracy table fails the verification** (Knut, #182). On a verification printed through its profile, the five figures of the Profile accuracy table (average, lowest 95 %, highest 5 %, maximum, and the 95th percentile, each against the profile's own prediction) now count towards the sheet's overall verdict: one of them over its limit makes the sheet FAIL. Before, the table had its own words and did not change the verdict.
- **Verifications printed with the perceptual or saturation intent are judged on the profile's accuracy** (Knut, #182, following industry practice: ICC White Papers 9 and 27, ArgyllCMS profcheck). Those intents change colours on purpose, so comparing the print with the original colours cannot pass or fail it. That comparison is now shown for information, with a note naming the intent, and the sheet is judged on its Profile accuracy table. Relative and absolute colorimetric prints are judged exactly as before.
- **Guided charts are printed without the stamp** (Knut, confirmed by Sebastian). Guided has no "Stamp settings down the right edge" control; until now every Guided chart carried the stamp anyway.
- **The neighbour check is quieter and sees more on small charts** (Knut, #182, method "B2+"). A patch is now judged as soon as 2 patches near it in colour have been read in other strips (was 3), and it turns red only when it is the patch that is off, further from its own expected colour than its neighbours are from theirs. A good patch next to patches spoiled by a blocked nozzle or a drying ink stays unmarked. Measured on Knut's real sheets: 24 suspects at the default instead of 35; on small charts twice as many patches can be checked. The hover card says "Checked again after each strip: a patch can turn red later, when patches near it in colour are read".
- **Two buffers for the neighbour check** (Knut, #182). Preferences > Measurement has "Buffer on a chart made with a pre-conditioning profile" (default 5 ΔE) beside "Buffer on a chart with estimated colours (most charts)" (default 10 ΔE). The chart decides which applies. If you had changed the earlier single buffer, your value is kept for both, so the check on pre-conditioning-profile charts does not become stricter without you choosing it; at the old default you get 10 and 5.
- **The strip test and the neighbour check are named, and the neighbour check has its own switch** (Knut, #182). The checkbox that read "When reading strips, only flag a patch that also stands out from its own strip" is now "Strip test: ..."; it never controlled the neighbour check, and switching it off can only add red outlines. The new checkbox "Neighbour check: flag a patch that does not fit the patches nearest to it in colour" switches the neighbour check: off with OK, its red outlines go at once, also during a measurement; on again, they come back, and what a re-read confirmed (yellow) or corrected (green) is kept. Both help cards say exactly what each does, needs and cannot do.
- **"Which presets can be used for verification?" counts each preset two ways** (Knut, #182). Next to the count with the preset's own colours there is now the count when the preset is filled From Profile Gamut, checked for every built-in preset before each release. 162 of the 189 built-in presets answer all 18 metrics that way; with their own colours none can, because only a chart filled From Profile Gamut prints its solid patches as they are.
- **The Verification box opens on the latest dated verification** (Knut, #182). With Run type Verification, choosing a run or switching to Verification selects the run's most recent dated verification, so its measurement shows on the Measure tab at once; "New verification" is selected only when the run has none. Selecting a dated verification asks nothing: "This chart already has a measurement" no longer opens on a mere selection (it still opens when you arrive at the Measure tab), and the questions before measuring into a date that holds readings, or changing a measured chart, are unchanged.
- **Every hover card compares the patch with its colour neighbours** (Knut, #182). Under "Measured", the card says how much further from (or closer to) its expected colour the patch is than the 2 to 4 patches nearest to it in colour are from theirs (the median), flagged or not, so a patch slightly off can be told from a good one. On verification and calibration charts the card shows the same comparison, but the neighbour check outlines nothing there.
- **Ukrainian: "paper white" is "білизна паперу" in 55 more texts** (help texts, report notes, Preferences), where it read as "white paper".

### Fixed (review of beta 15)

- A report saved by an earlier beta, whose verdict did not count the Profile accuracy table, keeps the table's earlier note, so it never claims that a failed figure there failed the sheet.
- "Save as defaults" pressed in Guided no longer switches off Manual's "Stamp settings down the right edge".
- The presets window's two count headings are on two lines, so the preset names are no longer cut short; a built-in preset without a current certificate reads "Unknown" instead of "Built-in presets only".
- The preview's switch closes when the pointer rests near it over another window.
- The Verification box shows a selected date as the date ("2027-01-07 11:00"), not "Overwrite 2027-01-07 11:00": choosing a date to look at it is not an overwrite, and measuring over a date that holds readings is still asked about at Start Measurement. The date is no longer cut off in the bar: when the bar is short of room, the Run box gives way first.
- A changed neighbour buffer from beta 14 or earlier now carries over to both new buffers.
- The hover card's line "Checked again after each strip: a patch can turn red later, when patches near it in colour are read" is broken over three lines, so the red card keeps its usual width (it was about 500 px wide in every language). The words are unchanged.
- Translations of the new texts corrected in German, Dutch, Spanish, French, Italian, Norwegian, Portuguese, Swedish and Ukrainian (the rendering intent called by each language's usual name, the neighbour comparison's lines).

### Fixed (on-screen sweep of beta 15)

- **"Which presets can be used for verification?" shows the preset names again, and more of them.** The two count columns are headed "Own colours" and "From Profile Gamut", hold "16 of 18", and are only as wide as that; one line beside "Sort by" says that both count the metrics a chart answers, with the full explanation on hover (it was a four-line box over the list). Every preset name has its full name as a tooltip. Measured on screen at the window's size of 1179 x 730: names cut 6 in English and 21 in German (were 125 and 161; beta 14: 17 in English), rows shown 20 and 19 (were 14).
- **The main window fits a 13" MacBook Air.** Its smallest width followed the width it already had (the tab bar asked for its current width as its minimum), so a window at 1470 points could not be made narrower than 1474. It is now 900, as intended.
- The question for a printer model whose paper profiles ChromIQ does not know shows its title, "ChromIQ does not know this printer’s paper profiles yet", as the other questions do.
- Ukrainian: the credits say "Стало можливим завдяки Knut Georg Larsson" ("Made possible by"), and "Побудовано на ArgyllCMS" ("Built on"); both had read "Створено" ("Created").

## v4.3.3-beta.14

**The chart preview can show the paper's own tone: "Simulate paper white" in the preview's switch.**

### Added

- **Simulate paper white in the chart preview** (Basti, 2026-10-08). While the preview of Create Chart, Print Chart or Measure shows a page as on paper, hovering the small icon in its top right corner now also opens a "Paper white" button, like Photoshop's Simulate Paper Color. Ticked, the page is shown with the paper in its own tone, as the run's profile describes it (absolute colorimetric), so a cream or bluish paper looks cream or bluish and every colour sits on it as on the sheet; the page's blank margin and the frame round it take the same paper colour. Unticked, the paper is shown as white, as before. The button only switches the paper white, never the view, and is not there while the preview shows device values or before the run has a profile. A verification chart printed through the profile is still converted exactly as the print converts it; only the last step, from the paper to the screen, changes. ChromIQ remembers the choice for all three tabs; it starts off. With the keyboard, Tab from the switch to the button and press Space. Switching back and forth is instant once a page has been shown both ways, kept in memory only, and nothing printed changes.
- When the preview is too narrow for the button and the whole "As on paper" beside it (the splitter pulled far to the right, or a long language), the switch leaves the button out rather than open past the image or shorten its words to a letter; widen the preview to reach it again. The keyboard help names the keys in your language ("Tab · Leertaste").

### Changed

- **Ukrainian: "paper white" is now "білизна паперу" throughout the short labels** (the Paper white button, Simulate paper white in the soft-proof tool, and the report's paper white headings), as Russian has it. Before, it read as "white paper", and two labels were cut off or ungrammatical ("Відносно паперу біл").

## v4.3.3-beta.13

**Fixes for small screens: the preview's switch on the Print Chart tab sits in the right place from the start, Preferences fits a 13" MacBook Air, and the "Approximate colours" note no longer jumps over the controls when the window is resized.**

### Fixed

- **The preview's switch sits in the right place on the Print Chart tab from the start** (Basti, 2026-10-08). On first opening the Print Chart tab, the small paper or screen icon in the preview's top right corner sat 13 px too high, on the "PRINT PREVIEW" heading, and only moved to its place after a click. The preview's heading grows by the chart's name once the tab is on screen, which moves the image down after the icon had been placed. The icon now follows the image itself, so it is in the same place on Create Chart, Print Chart and Measure from the first moment, at any window size.
- **Preferences fits a small screen** (Basti, 2026-10-08, a 13" MacBook Air). The window opened at a fixed minimum size taller than such a screen's usable area, so its top touched the menu bar and OK and Cancel were just below the bottom of the screen. It now never opens larger than the usable part of the screen (without the menu bar and the Dock or taskbar), less a small margin, and is placed fully on it; the pages scroll inside it and the button row always shows. On a larger screen it opens at the same size as before.
- **Preferences dragged to a smaller display can be made to fit it** (beta-13 review). Opened on a large display and dragged to a 13" one, the window kept the large display's minimum size, so it could not be made small enough to show OK and Cancel. Moving it to another display now lowers that minimum to the new screen and shrinks the window if it is too tall.
- **The "Approximate colours" note on a preview stays at the top right of the image** (beta-13 review). It is placed there when it appears (since #125, so it never covers the controls below the preview), but any resize of the window moved it to the bottom right of the preview, over "Page 1 / 1" and the panel below. It now stays on the image, like the preview's switch.

## v4.3.3-beta.12

**A verification printed through its profile is judged against the right colours, with a new Profile accuracy table; Knut's re-read rules (green, yellow, red) are complete; the chart preview shows the sheet as it will print, with a switch (or ⌘Y / Ctrl+Y) to the raw device values; the computer stays awake while you measure; built-in presets no longer switch the stamp on, and a new target starts with it off.**

### Added

- **The computer stays awake while you measure** (Basti, #182 6015495063). While a measurement is running, neither the display nor the computer goes to sleep, also during long pauses between strips. As soon as the measurement ends, however it ends (finished, failed, stopped, or ChromIQ closed), your normal sleep settings apply again. On macOS ChromIQ uses the system's own caffeinate, tied to ChromIQ so it can never be left running; on Windows the system's execution-state setting; on Linux systemd-inhibit where it is installed.

### Changed

- **"Which presets can be used for verification?" knows its answers at once** (#182, Knut 6045500910). Every built-in preset now ships with a certificate of how many of the metrics its chart can answer, so the window and the check when you choose Verification no longer lay the preset's chart out first. Your own presets get a certificate the first time they are checked, kept in ChromIQ's settings folder; it is made again when you change the preset, and removed when you delete it. A certificate made by another ChromIQ version, or for a preset that has changed since, is never used.
- **A verification printed through its profile is judged against the right colours, and its profile is judged too** (#182, Knut 6045500910; Basti 6022393918). The Measurement Report compared such a sheet with the chart file's own colour estimate, which is not the sRGB the print was converted from (its blacks are lighter: up to ΔE00 6.9 apart), and decided which colours the printer can reach in absolute colorimetry, although the sheet was printed and judged relative to its paper. Now the colour figures compare every colour inside the profile's gamut with the colour the sheet was converted from (for example sRGB.icm), with the gamut tested in the print's own intent; the colours beyond the gamut are still listed but never fail a limit. A new "Profile accuracy" table also compares every patch with what the profile predicts for the ink amounts that were really printed, with the same limits. Basti's verification of 6 October now reads average 0.77 and maximum 3.66 within the gamut (was 1.50 and 5.27), and the profile itself average 0.51, maximum 2.13. Sheets printed raw, such as a From Profile Gamut chart, are judged exactly as before.
- **"Stamp settings down the right edge" is off on a new target** (#182, Knut 6045500910). A chart target with nothing stored used to open with the stamp on, so a new verification chart came out with the settings printed down its right edge unless you unticked it. It now opens with the stamp off. A target that already has the stamp stored keeps it, and if you saved your defaults with the stamp ticked, a new target follows your saved defaults.
- **A re-read is compared with every earlier reading of the patch, as Knut ruled** (#182, Knut 6045500910). For a patch outlined red because it reached your limit: a re-read that reads the same colour as before (within ΔE 3) is yellow, as before. A re-read that is past the limit again but clearly different, higher or lower, stays red, and its card now says so: "Red outline: the readings do not agree / ΔE*ab 150.4 now; before: 120.3 / The two readings are not similar, / and both are past your limit 95.0. / Read it again: a reading that matches / one of them shows which value is real." Similar patches and a learned colour range no longer turn such a patch yellow, because one of its readings is a misread. A third reading that matches ANY earlier one, not only the one just before it, is yellow with the usual card: Basti's J28 read 69.5, then a misread of 150.4, then 69.7, and is now yellow instead of staying red. A re-read under the limit after a reading past it is green, also when the two readings are close (96, then 94, at a limit of 95).
- **A preset chosen in the From Profile Gamut module gives the chart its layout, not its colours** (Basti, #182 6036695078). On a verification, picking a built-in preset in From Profile Gamut used to build that preset's own patches, which are made for profiling, and left "Colours to test" where it was. Now the preset only lays out the page (paper, patch size, strips, margins), "Auto, fill the pages" is switched on, and the chart is filled with colours from your profile's gamut plus the 8 cube corners: the A3 Plus 616-patch preset gives 608 colours + 8 corners. Picking a preset in Manual, or for a profiling chart, works as before.
- **The chart preview looks the way the sheet will print** (#182, Knut 6045500910, Basti 6045468325). Create Chart, Print Chart and Measure painted a chart's ink amounts straight onto the screen as colours, so the chart looked lighter and brighter than the paper (on Basti's verification chart 5.5 L* lighter on average, 20 at the worst). Once a run has a profile, the preview now shows the chart through that profile, the way the printer lays it down: a profiling chart and a From Profile Gamut chart as they are printed (raw), and a verification chart printed through the profile converted exactly as the print converts it first. Which way a verification chart prints comes from the Print Chart tab's Colour row, and once it has been printed from its print record. A small label in the preview's top right corner says what you see: "As on paper, via the run's profile", "As on paper, printed through the profile", or "Device values, no profile yet" before there is a profile; hover it for the details. The paper is shown as white. Each page is worked out once and kept, and nothing about what is printed changes.
- **The preview's indicator switches between "as on paper" and "device values"** (Basti, 2026-10-08). The small label in the chart preview's corner is now just an icon, a sheet of paper or a small screen; hover it and it slides open to say what you see ("As on paper", "Device values") and what a click does. A click, or ⌘Y (Ctrl+Y on Windows and Linux, the key Photoshop uses for Proof Colors), switches the preview of Create Chart, Print Chart and Measure between the chart as it will print and the ink amounts in the file shown as screen colours. ChromIQ remembers the choice. Before a run has a profile the indicator shows the screen and a click does nothing. Switching is instant once a page has been shown both ways, and the preview is now worked out in memory, about twice as fast as before and with exactly the same pixels, leaving no files behind. Nothing printed changes.
- **"Strip Read Quickly" allows a little room** (Basti, #182 6001610646). A strip read up to 2 % faster than your instrument's limit (8 ms a patch at 400 ms, about a fifth of a second over a 28-patch strip) no longer brings up the Re-read / Continue window or the slow-down sound; it is reported as close to the limit instead. Basti's strip, 398 ms against 400, was within that. The reading time is measured on the computer's clock between the instrument's ready beep and the strip arriving, and each of those passes through the reading engine and the app's event queue first, so 2 % is about what the clock itself can be off. A strip read faster than that is still warned about exactly as before.

### Fixed

- **The lower reading-direction arrow in the Measure tab no longer covers the bottom row of patches** (Basti, #182 6001610646). When you read strips in both directions, the second arrow now sits just below the patches, in the chart's bottom margin (where it may cover the help marks printed there), and is made shorter when that margin is narrow. Only a chart with almost no paper under its patches keeps it at the sheet's bottom edge.
- **Every built-in preset switches "Stamp settings down the right edge" off** (#182). Most presets did not say anything about the stamp, so a chart built from one kept whatever the box held, and on a new target that is on: Basti's A3 Plus 616 verification chart came out with the stamp, and on the CR30 hexagon charts the stamp ran over the patches. All 189 built-in presets now set it off, as they were designed. Your own saved presets keep their setting.
- **A verification with no colour inside the profile's gamut no longer fails on the colours outside it** (#182, beta-12 review). The colours beyond the gamut are never judged against a limit, but when not a single patch of the sheet lay inside the gamut, the report judged all of them anyway, and the sheet failed. Its colour-accuracy and evenness rows now say "no patch of the measured chart lies inside the profile's gamut" and judge nothing.
- **A corrected misread turns green even when the re-read was still under suspicion** (#182, Basti 6002595728). A patch outlined red whose re-read was fine stayed red, and later lost its outline without ever turning green, when the neighbour check still suspected the re-read because the strips around it had not been read yet (Basti's AA5 and AA16). ChromIQ now remembers that the re-read read a different colour, and turns the patch green as soon as nothing flags it any more. Reading the misread colour again cancels that.
- **Japanese and Chinese call the pre-conditioning profile by one name.** The Create Chart field said 前処理プロファイル / 预处理配置文件 while the button next to it, the targen row and the newer texts said プレコンディショニング / 预调节. Every pre-conditioning text now uses the second, the term the rest of each translation already used.
- **Texts that send you to a tab name it as the tab bar does.** Polish said "Drukuj wzorzec" and "Pomiar" for the tabs "Wydrukuj wzorzec" and "Zmierz"; Russian, Ukrainian and Dutch named the Build Profile and Measure tabs by other words than their titles. All 13 languages were checked.
- **"Go to the Build Profile tab" names the tab as the tab bar does.** After a measurement, the button and the text that send you on to tab 4 took the name of the Build Profile BUTTON, which in Russian, Ukrainian and German is not the tab's title (Russian said "Собрать профиль" for the tab "Сборка профиля"). More tab names in Polish, Russian, Ukrainian and Dutch texts were corrected too, among them some still in English in Ukrainian.
- **The highlighted button of a window no longer loses a letter at each end.** The recommended button is drawn in bold, but its width was worked out for regular type, so a long label was cut at both ends, and in the "taking longer than usual" window it also ran under Cancel (seen in Russian and Ukrainian).
- **The "taking longer than usual" window only talks about what your chart uses.** During a chart built without a pre-conditioning profile (a plain CMYK chart, for example) it spoke of pre-conditioning profiles and refinement charts; it now explains the slowdown and the faster layout without them. A chart built with a profile shows the same text as before.
- **A chart that targen could not build shows targen's whole message.** The window quoted only "targen: Error -", because ArgyllCMS writes its message in two pieces; it now quotes the sentence that follows too.
- **The true-colour preview of a CMYK chart leaves no files behind, not even after a crash.** Its converted pages were kept in a temporary folder until ChromIQ quit, so a crash or Force Quit left that folder on the disk. They are now kept in memory, and a folder left by a ChromIQ that was killed in the middle of a conversion is removed the next time ChromIQ converts a page.
- **The chart preview prepares the other pages once, not once per tab.** Create Chart, Print Chart and Measure each started their own background work to make the chart's pages ready "as on paper", for the same chart. They now share one, which saves processor time on a large chart; switching the view is as fast as before and the pages look exactly the same.

## v4.3.3-beta.11

**A new neighbour check outlines misreads the limit cannot see, a misread corrected by a re-read turns green, verifications get their own limit (ΔE 10), charts made with a pre-conditioning profile get ΔE 20, the help says what the limits are for, charts look the same on every computer, and Create Chart no longer fails at an ink limit of 300.**

### Added

- **The neighbour check: a misread the limit cannot see is outlined red** (#182, Knut 5983470377 answer 5, 5983725218 and 5984174575). On a profiling chart, with estimated colours or made with a pre-conditioning profile, each patch is compared with the 3 or 4 patches nearest to it in expected colour that were read in other strips. When its reading is further from theirs than their expected colours are, by more than ΔE 10 (median), it is outlined red, even far below the limit, and its card says why with the numbers: "Its reading does not fit the 4 patches / nearest in colour, read in other strips: / it is ΔE 12.4 further from their readings / than the expected colours are (your limit 10.0). / Probably a misread." Read it again: the same colour twice turns it yellow. Only its own re-read does that: similar patches and a learned colour range, which can turn a patch over the limit yellow, do not clear a neighbour suspect, also when it is over the limit as well. It is judged again after every strip and patch and when a measurement is opened, and never flags a patch for lack of comparisons. Not on a verification or a calibration chart. On Knut's and two inkjet profiling charts (5,323 patches) it outlines 35 good patches (0.7 %) and catches most single glitches and every strip read out of step.
- **Preferences ▸ Measurement: "Flag a patch that does not fit the patches nearest in colour by more than:"**, default ΔE 10 (Knut 5983725218). Changing it and pressing OK outlines the preview again.
- **The closing window of a measurement sums up the suspected misreads** (Knut 5983470377): the patches the neighbour check still outlines red, those a re-read kept as real, how many patches could be checked, and, when "Was a strip read twice?" ran, which strips it asked about and what you answered. Under the reading times, on profiling and calibration measurements; never on a verification.
- **Green outline: a misread corrected by a re-read** (#182, Knut 5984277558). A patch that was outlined red, by the limit or by the neighbour check, and whose re-read now fits is outlined green, and its card says: "Green outline: corrected by a re-read / The first reading (ΔE 58 off) / did not fit; the new one does. / It replaces the misread." The closing window adds "2 misreads corrected by a re-read: patches Y6, AE8." Green is kept with the measurement and shown again when you open it; reading the patch once more with a reading that is outlined again ends it. On verifications too (the card only; their closing window has no misread summary). The overlay help, the hover help and Preferences ▸ Measurement explain it.

### Changed

- **A verification measured against its profile's prediction has its own limit, ΔE 10** (#182, Knut 5983470377: "yes, 10, and own threshold row"). Preferences ▸ Measurement, "Flag a patch when its colour error reaches:", has a third row, "on a verification judged against its profile". It is used exactly when a verification chart ChromIQ printed is compared with what the run's profile predicts for it; until now such a chart took the limit for a chart made with a pre-conditioning profile (30). The strip option still does not apply to it. A verification that falls back to the chart's estimate keeps the limit its chart names. Nobody's earlier limit is carried into the new row. The help and the defaults line say so. Translated in all 13 languages.
- **The help says what the red-outline limits are for** (#182, Knut 5983733592). In Preferences ▸ Measurement and in the Measure tab's hover help, one paragraph now explains that the red outline is there to catch misreads so you read the patch again, not to mark colours your printer cannot reproduce (a re-read or similar patches turn those yellow), and why each limit sits where it does: 95 for estimated colours, which are far from any real print (the strip check and the neighbour check do most of the misread hunting there), 20 for a chart made with a pre-conditioning profile and 10 for a verification, whose expected colours are close to what the printer should print. Translated in all 13 languages.
- **The limit for a chart made with a pre-conditioning profile is ΔE 20, no longer 30** (#182, Knut 5983470377: "If your tests indicate 20, then use it"). It applies to charts whose file carries ArgyllCMS's ACCURATE_EXPECTED_VALUES, which targen writes only when it is given a pre-conditioning profile (a chart made after "Use as pre-conditioning profile", or with Manual targen -c). If you never changed it, you get 20. A value you chose is kept, except 30: a stored 30 cannot be told apart from the old default, which Preferences saved along with everything else, so it becomes 20 too; set it back if you meant it.
- **Charts made with a pre-conditioning profile are called that** (#182, Knut 5984174575). The charts whose expected colours are accurate (targen -c; the chart file carries ACCURATE_EXPECTED_VALUES) were called "a chart made from a profile", which reads like a FROM PROFILE GAMUT chart. The Preferences ▸ Measurement row and its tooltip, the limits help in Preferences and in the Measure tab, and the hover card's limit name now say "made with a pre-conditioning profile", in all 13 languages. FROM PROFILE GAMUT charts and verifications judged against their profile keep their names.
- **Purple is part of blue** (#182, Knut 5983470377). The colour ranges a yellow outline learns from no longer have a purple/violet range: blue now runs from 240° to 325° and magenta stays. On Knut's charts, re-read in full, the patches that were purple now learn from the blue ones, which saves re-reads (at limit 50: 16 → 14, 20 → 15 and 12 → 10 on his three charts) and leaves no patch red that was not before.
- **A verification whose profile is newer than the print says so on its hover card** (#182, Knut 5983480953). When the run's profile was made, or changed, after the verification sheet was printed, ChromIQ cannot use the profile's prediction for that print and compares with the chart's own estimate instead, but the card still used the profiling wording that ends "keep it for the profile". Its red card now says "Far from the chart's estimate. The profile was made after this sheet was printed, so its prediction is not used. Either a misread, or a real difference: read it again to find out." (Knut's approved wording), and "Same value after a re-read: it is real: the print differs from the chart's estimate here."; a yellow card says "A real difference from the chart's estimate, not a misread." Translated in all 13 languages.
- **Charts come out the same on every computer** (Basti, 2026-10-05). How ChromIQ spaced the letters of a chart's labels and text depended on whether a text library (FriBiDi) happened to be installed on the computer, so the same chart could come out a fraction of a millimetre different on two Macs. It now always lays text out the same way, the way most computers already did. On a few Macs the label spacing changes very slightly, and on a chart that sizes its patches to fit the page a patch can come out a hundredth of a millimetre different. Charts already printed and measured are not affected.

### Fixed

- **Windows: renaming a project only by upper/lower case renames its folder too** (found by ChromIQ's new test runs on Windows). The folder kept its old spelling.
- **Create Chart no longer fails with an ink limit of 300 and grey steps** (F-10, #182 5985477496, found by the profile-engine research). ArgyllCMS 3.5.0 targen stopped with "ofps: assert" (or "Failed to re-seed the voronoi") whenever a fixed patch sat on a corner of the device cube exactly at the ink limit: ticking Total Ink Limit (it starts at 300) on a CMYK chart and setting Grey Axis Steps above 0 was enough, and so were single-ink steps at 100, and cube or surface grids (-m, -M, -b) at 100, 200 or 300, on RGB and CMY too. In exactly those cases ChromIQ now hands targen the limit plus 0.1 (300.1), which keeps every patch you asked for, and the log says so. Your setting, the command stamped on the sheet, and the chart's recorded ink limit (and so the profile's colprof -l) keep the value you chose. Any other limit (250, 320, ...) goes to targen unchanged. A limit below 100 with single-ink steps still fails in targen, for a different reason.

## v4.3.3-beta.10

**Red cards say exactly why a patch stayed red, a colour whose reading lands where its confirmed patches' readings did turns yellow, a verification's card speaks of the profile's accuracy, an unplugged instrument no longer floods the log, Build Profile offers only what colprof accepts, and three Windows/Linux fixes from ChromIQ's new test runs on those systems.**

### Fixed

- **An instrument unplugged during a measurement no longer floods the log.** Knut's beta-8 logs held about 255,000 copies of `icoms_usb_transaction: ReadPipeAsync failed with 0xe00002c0` from one minute (Argyll's USB layer repeating itself until the run was stopped, and every line logged twice), which pushed the rest of the session out of the five log files. Identical lines are now collapsed where the tool's output enters ChromIQ: the line and its first three repeats are shown as before, the rest are counted, and a line such as `[ChromIQ: the line shown above came 127496 more times, not shown]` reports them, at most once every five seconds while it goes on and once when it stops. Engine events and lines that differ in any way (profile checks, progress) are never collapsed. The disconnection is reported exactly as before, because the first line still reaches everything that reacts to it. Replaying 127,500 such lines: 1.9 s and 29.3 MB (258,740 log lines) before, 0.08 s and 16 log lines after.
- **The collapsed-line summary is no longer read as one more of the line.** It quoted the line word for word, so anything in ChromIQ that reacts to that line (the unplugged-instrument check, for one) counted the summary as another occurrence. The summary no longer quotes the line (it was shown word for word just above it), so nothing that searches the tool's output matches it, and it is plain text that can be searched and copied. Two lines flooding in turn share one summary. A single hidden repeat is now shown as the line itself instead of "came 1 more time", and the first summary of a flood no longer comes after a single repeat because the run had been quiet for a while. A flood that ends because the tool goes quiet is now summed up two seconds later, instead of only when the next line arrives (which could be minutes later), and always before the run's end is reported.
- **Build Profile no longer offers an illuminant that stops the build** (D-10, Basti 2026-10-04: every control with the profile engine off offers only what ArgyllCMS colprof accepts). The Illuminant (-i) and FWA (-f) lists in Guided and Manual offered "D65M2 (D65 with UV filter)", which colprof 3.5.0 does not know: it printed its usage text and stopped, and no profile was built. D65M2 is gone from both lists. A D65M2 remembered from before (saved defaults, a preset, a target's settings) is read as D65, and the log says so.
- **Linux: the measuring helper ends when a measurement ends** (found by the new test runs on Linux). It kept waiting after a measurement was saved or stopped, so anything waiting for it waited until it was killed.
- **Windows: a read-only profile or measurement is repaired too** (found by the new test runs on Windows). The repair was skipped in silence when the file was read-only.
- **Linux: the folder diagram on the File Structure help card lines up** (it asked for a monospace font Linux does not have).
- **Windows: the release ships the same data files as macOS and Linux.** The Windows build changed their line endings on the way.
- **Dark Region Emphasis (-V) stops at 3.0**, the most colprof accepts (it refused 3.1 to 4.0 with its usage text). A remembered value above 3.0 becomes 3.0, and the log says so. The same holds in the Advanced settings of "Build profile with scanner or camera", which also runs colprof, and every colprof build clamps a stored value it is handed.

### Changed

- **A red patch in a colour range that has learned says why it stayed red** (#182, Knut 5982206917). Its hover card said only "This range has learned, but this one is off in a different way." It now names the test that ruled the patch out against the confirmed patches of its range, with the numbers: its error is smaller ("ΔE 63.8 to 64.3 here, ΔE 74.8 to 92.4 on its confirmed patches, at most ΔE 10 smaller allowed"), it points another way ("ΔE 15 to 27 sideways, at most ΔE 10 allowed"), or it stands out from its strip more. When one test does not rule out every confirmed patch, the fewest tests that do are named. Nothing about which patches are red or yellow changes. Knut's O7 at limit 60 now reads "one's error is smaller: ΔE 64 here, ΔE 75 to 92 on its confirmed patches". Knut kept the "smaller" test (5982600086), with the waiver below. Translated in all 13 languages.
- **A red patch whose reading lands where its confirmed patches' readings did turns yellow** (#182, Knut 5982600086 approving 5982339631). Knut's O7 was red only because its error was more than ΔE 10 smaller than its range's confirmed patches'. But a printer that cannot reach a colour lands its readings at the same place, the edge of what it can print, so a less vivid colour asked for has a smaller error and the same reading. The "as large or larger" test stays, as Knut wanted, but is waived when the patch's measured colour is within ΔE 15 of a confirmed patch's measured colour; the other two tests (the same direction, not standing out from its strip much more) still apply. On Knut's 1944-patch chart with his re-reads: red 4 → 0 at limit 60 (O7, J25, BG5, Y27 turn yellow), 10 → 3 at 50, 19 → 6 at 40. In the replay with injected misreads (out of step, wrong strip, smudge; 40 trials each, limits 60 and 50) not one misread more turns yellow. The yellow card of such a patch says "Its reading landed where its confirmed patches' readings did."; a red "smaller" card now also says that its reading did not land near theirs, and how far away it was ("ΔE 18 to 31 away, at most ΔE 15"). Translated in all 13 languages.
- **A verification's hover card speaks of the profile, not of what the printer cannot reach** (#203, Knut 5982702169). On a verification measured against the profile's prediction, a highlighted patch is a check of the profile's accuracy, yet its card said "Either a misread, or a colour this printer and paper cannot reach" and "Keep it for the profile", though a verification never goes into a profile. Such a card now says "Far from what the profile predicts. Either a misread, or a place where the profile is inaccurate." (red), "A real difference, not a misread: the profile does not predict this colour well here (or the printer has changed since the profile was made)." (yellow), "Same value after a re-read: it is real, and counts against the profile's accuracy.", and "The profile is off in the same way here" on a learned card. Profiling cards are unchanged. Wording approved by Knut (5982788316). Translated in all 13 languages.
- **The red and yellow help says exactly when a yellow outline holds.** A patch confirmed by a re-read is no longer "never forgotten": the help now says the confirmation is kept when you change the limits, and ends only when you read that patch once more and the new reading is not outlined or gives a different colour. The "learned from its colour range" rule now names, in the hover help and in Preferences alike, that the patch must be off in the same way as a confirmed patch of its range and must not stand out from its strip much more than that patch did. Translated in all 13 languages.

## v4.3.3-beta.9

**Similar patches in different strips confirm each other, so a colour your printer cannot reach turns yellow without re-reading every strip; a colour range learns at three confirmations, however close; the outlines follow a changed limit at once; Check & Refine judges every patch through the profile, whatever its outline; the help explains red and yellow everywhere; and the Check & Refine window fits smaller screens.**

### Changed

- **Similar patches confirm each other, like a re-read** (#182, Knut 5979886227). Two patches with a red outline turn yellow together when they were read in different strips, were expected to be nearly the same colour (less than ΔE 6 apart) and are off in the same way (their errors agree within ΔE 10). A misread does not repeat itself like that in two separate passes of the reader; a colour the printer cannot reach does. Patches of one strip never confirm each other, because one smudge or one slipped strip can make several of them wrong alike. On Knut's 1944-patch chart at the default limit, all 18 red patches (the sRGB blue corner) are now confirmed without a single re-read; at ΔE 50, 10 of 129 stay red where his 27 re-reads left 61. The hover card says "Yellow outline: confirmed by similar patches" and names them. Confirming by a re-read works as before.
- **A colour range learns at three confirmed patches, with no ΔE 6 spacing between them.** This retracts the beta-8 note that "the four magenta patches are the same corner colour (all within ΔE 4.7), so they count as one": Knut ruled that wrong, and they now count as four. Confirmations by a re-read and by similar patches count together. A patch judged "like" a confirmed one still never confirms anything itself. The beta-8 card lines "Patches closer than ΔE 6 in colour count as one confirmation ..." are gone with the spacing.
- **The outlines follow a changed limit straight away.** Closing Preferences with OK, or coming back to the Measure tab, judges every outline again from the measurement and the current limit, while the overlay is shown and no measurement runs. Lowering a limit can turn a pair of similar patches yellow; raising it turns them back.
- **Check & Refine is no longer influenced by red or yellow outlines at all** (#182, Knut 5980560281). Its purpose, in Knut's words: it checks the measurement through the built profile, and every high error it finds is used for the refinement recommendations. So a patch confirmed by a re-read or by similar patches is now offered for re-measuring like any other patch above the limit, and the window's "Not offered again, because ... already confirmed" line is gone. This reverses the beta-7 change "Patches a re-read already confirmed (yellow) are not offered again by Check & Refine". The confirmed patches are still remembered for the Measure tab's outlines.
- **The help says plainly what red and yellow mean** (#182, Knut 5980576263). Red: the reading is far from what the chart expects and may be a misread, so read it again. Yellow: the difference is real (confirmed by a re-read, by similar patches in other strips, or learned by its colour range), so keep it and do not read it again. The help of the overlay box, "Each patch shows", "Show patch values on hover", Preferences ▸ Measurement and the Getting started card all say so, together with what the limits do, that the outlines are worked out again when the limits change, and that Check & Refine judges on its own. Every red hover card now says "Read it again to find out.", every yellow one "No need to read it again." The Preferences help and the hover help still described the ΔE 6 spacing removed earlier in this beta; corrected.

### Fixed

- **Check & Refine's result window fits smaller screens** (Basti). With many strips listed it grew to the full height of its text, taller than a 13-inch MacBook or a 1366x768 laptop, could not be made smaller, and its buttons fell off the bottom of the screen. The window now never grows taller than the usable part of its screen (without the menu bar, a visible Dock or the taskbar): the grade and the numbers stay at the top, the buttons at the bottom, and the strip lists between them scroll when they do not fit. On a screen with room it looks as before, with no scroll bar.
- **Raising the flag limit no longer forgets a re-read confirmation.** A patch confirmed by a re-read that a higher limit no longer flags lost its confirmation, and a measurement resumed in that state saved the loss. The confirmation is now only hidden while the limit hides it, and comes back when the limit is lowered.

## v4.3.3-beta.8

**A wrongly read strip is set aside until you read it again, ⌘Q / Ctrl+Q quits, the calibration help now says correctly when to use Apply Calibration, and a verification's progress bar no longer drops to 0 % when it is finished.** Fixes for Knut's beta-7 findings (#182) and for a forum report.

**For ajaytanna (printerknowledge.com):** a calibration chart is always printed in order, on purpose: each ink's ramp sits on its own strip. The "Randomise patch order" box is now greyed out for a calibration chart, and its tooltip says why. Profiling charts still randomise. With **Apply & Embed (-K)** you also click **Apply Calibration** after Build Profile, because colprof never puts the calibration into the profile. Our help text said the opposite and is corrected.

### Fixed

- **⌘Q quits ChromIQ on macOS, Ctrl+Q on Windows and Linux** (Knut, #182 5973222284). ChromIQ had no quit shortcut of its own, so ⌘Q was left to the app menu macOS gets by default, and it did not quit for him. Quitting now has its own shortcut, and Windows' own Alt+F4 works as before. Every way of quitting goes through the window's close, so a running measurement is asked about first, exactly as the close button asks. The keyboard shortcuts card (in Help and when printed) lists the quit keys in each system's own words: ⌘Q on macOS, Alt+F4 and Ctrl+Q on Windows, Ctrl+Q on Linux.
- **ChromIQ can always be closed, and says so in its log when it is not** (Knut, #182 5973449121). Once neither the window's close button nor quitting closed ChromIQ, and the log said nothing. Measured since: while any window that waits for an answer is open, a click on the main window's close button is dropped before ChromIQ hears of it, so a forgotten or hidden window kept the app open in silence. Quitting now closes such a window first, the log names every such window as it opens and every reason a close is refused, and a step of closing down that fails can no longer keep the window open.
- **Profile Description is one field in Guided and Manual** (Knut, #182 5973177088). Deleting the text in Guided gave the automatic name back there but not in Manual, and deleting it in Manual did not give it back at all. The two modes now show one Profile Description, and the manufacturer, model and copyright fields with their switches are shared the same way. Emptying the field in either mode always brings back the automatic name.
- **The Calibration complete window at the start of a measurement lists every key** (Knut, #182 5971383600). After the calibration that starts a resumed strip measurement, the window showed only two key hints, far apart at its bottom, while the window after a K calibration listed all of them. It now shows the same key list (f, b, n, K, d, Esc / q).
- **"No instrument found" tells the truth when no instrument is connected** (Knut, #182 5969949735). When ChromIQ refuses to start because nothing is connected, the window came after a second and still said the instrument "has not replied for 5 seconds" and suggested turning off "Faster instrument connection". That case now has its own plain text: no measuring instrument is connected; connect it and press Start again. The original window is unchanged for an instrument that really does not answer.
- **The calibration help now says when to use Apply Calibration** (Basti). It said a chart made with the calibration applied to its patches (-K) needs no Apply Calibration afterwards. ArgyllCMS says the opposite: colprof never puts the calibration into the profile, so when your printer cannot calibrate itself (-K) you click Apply Calibration after Build Profile and print with the calibrated profile. When your printer or RIP applies the calibration itself (-I), you do not, because the colour would be corrected twice. The Calibration & Profiling help, the windows after Create Calibration File and Build Profile, the -K and -I tooltips and the calibration card in Help now all say this.
- **"Randomise patch order" is greyed while Run type is Calibration** (forum report, ajaytanna). A calibration chart is always laid out in order, so each ink's ramp sits on its own strip, but the box still looked switched on and changeable. It and the seed controls (and the "Preserve Patch Order" row) are now greyed for a calibration chart, with the reason as their tooltip. Your setting is not changed: profiling charts keep randomising exactly as before.
- **"Was a strip read twice?" kept asking after you moved to the strip you had read** (#182, Knut 5969949735). With the reader on strip A, reading strip B filed B's colours as strip A, and the window rightly asked. If you then chose "Re-read strip A" but moved the reader to B and read B there, ChromIQ compared B with the reading still filed as A (which was B) and asked "Strip B looks very like strip A" again, on every re-read of B. A reading the window asked about, and you did not keep, is now set aside: it is never compared with again, and its strip counts as unread until you read it, so the chart is not called complete while strip A still holds strip B's colours (before, it could be saved that way, which is where the very high errors in that measurement report came from). The progress figure does not count it either, and when every other strip is read the reader goes back to it. If you stop before reading it, its readings are left out of the saved file, so the strip is still unread when you resume. The window also has a third answer, **I read strip B**: the reader goes to strip B to read it again there, and strip A waits to be read. Its wording is proposed and shows already.
- **A verification's progress bar fell to 0 % when the measurement was finished** (#182, Knut 5973177088). The bar counted the readings before they were moved into the verification's dated folder, so it found none and stayed at 0 %. It now counts them where they were filed, and shows 100 % for a complete verification. (During the measurement the bar counted correctly in every run we could make with the replay instrument, on Knut's own project, including his route Create Chart, Print, Measure; if it stays at 0 % while you read, please send the log.)
- **The hover card now says why a colour range has fewer spaced confirmations than yellow patches** (#182, Knut 5969949735, 5973177088). The counts were right by the approved rule (three confirmed patches at least ΔE 6 apart): on run 4, blue patches A6 and L1 are only ΔE 2.9 apart, so A6, E1 and L1 count as two; on the 1944-patch chart, the four magenta patches are the same corner colour (all within ΔE 4.7), so they count as one. A card whose range has not learned yet now lists the confirmed patches and, when some of them count as one, says "Patches closer than ΔE 6 in colour count as one confirmation, so the range needs more different colours." Every one of the 13 colour ranges is tested to register re-read confirmations and to learn at three spaced ones, both for RGB charts and for charts judged by their expected colours, and every card message is tested. The purple cards differ because some purple patches are confirmed by a re-read and others are judged like a confirmed one; both are correct. *(Changed in beta 9: Knut ruled that close patches counting as one was wrong, so the ΔE 6 spacing and these card lines are gone; see v4.3.3-beta.9.)*

## v4.3.3-beta.7

**Check & Refine always offers refinement and says which strips to re-measure first and why; ChromIQ notices a strip read twice; press K to calibrate again during a measurement; verification sheets are judged against what your profile predicts; and fixes for CMYK charts with a printer calibration, for strip and patch patterns, and for Run type Calibration.**

**For ajaytanna (CMYK, CR30 and PrintFab, printerknowledge.com):** thank you for the report and the screenshots. All three problems are fixed. Picking the CR30 preset now sets Device Type to what its patches really are (RGB), and if your CMYK calibration does not fit that, a window tells you how to get a CMYK chart ("Edit patch recipe", then Device Type CMYK). The profile build failed because ChromIQ's measuring engine wrote the printer calibration into the measurement as "nan" for every chart made with a calibration; that is fixed, and a measurement you already took is repaired automatically from its chart the next time you build (the original is kept in the "old" folder), so you do not need to measure the 450 patches again. And a CMYK measurement can now be imported into a CMYK run.

**For jctay (strip and patch patterns, printerknowledge.com):** thank you for finding this. The cause was in ChromIQ, not in your instrument or in ArgyllCMS: with strip pattern "0-9", ChromIQ printed labels like "10", "11" … that "0-9" cannot express. ChromIQ now follows ArgyllCMS's pattern rules exactly, and a pattern that cannot label your chart turns red before anything is built. The sheet you already printed can be read with ChromIQ's own measuring engine (Preferences ▸ Measurement, ChromIQ engine) without reprinting; ArgyllCMS's own chartread cannot read it, and ChromIQ now says so plainly instead of failing.

### New

- **Verifications from an earlier profile** (#182, Knut). When you choose Verification for a run whose profile was replaced after its verification measurements were made, or after its FROM PROFILE GAMUT chart was made, one window says so, with no sound. For old measurements and a FROM PROFILE GAMUT chart from the earlier profile, the default "Archive them and make a new chart from the current profile" moves the measurements and their reports to the "old" folder inside "verifications" and opens Create Chart on FROM PROFILE GAMUT with the run's last settings (the old chart moves when you press Generate Chart, as before, so the run is never left without a chart). For old measurements and an ordinary chart, "Archive them" moves them and opens Create Chart on that chart, so you can check it and go on to printing. When only the gamut chart is old, "Make a new chart from the current profile" opens Create Chart the same way. "Keep them" changes nothing and is asked again after ChromIQ is restarted. Quality_Check reports always stay. ChromIQ decides from the profile's own creation time, the date folders' names, the snapshot charts' creation times and each sheet's own print record, never from file times. The window waits while another window is open and never appears during Start or a measurement.
- **A verification sheet is checked against what your profile predicts (#182).** While a verification chart ChromIQ printed is measured, each patch is now compared with the run profile's prediction of the ink values that really went to the printer: the chart's own RGB for a raw print, the converted values for a print through the profile (any intent). The red outline then uses the limit for a chart made from a profile (ΔE 30 by default) and ignores the strip outlier setting, so a shifted or wrong strip is outlined even when the whole strip is off; the hover card says "Expected: profile prediction". The painting after a measurement uses the same values. On Knut's gamut sheet the pure-blue corner went from ΔE 105 to 2.2, and on a second printer's sheets the typical patch from about 28 to 4. ChromIQ keeps the old comparison (the sRGB estimate at ΔE 95) when it cannot know what was printed: a sheet printed outside ChromIQ, a run without a profile, a profile changed since the sheet was printed, a profile built under another light (an illuminant other than D50, another observer or FWA compensation), or a conversion that fails. chromiq.log says which was used and why. Approved by Knut (5964173774, 5964384250).
- **A CMYK or multi-ink measurement can be imported into a run whose chart has the same inks.** Measure → Import measurement (profiling and verification runs), Build Profile → Load measurement data and Check & Refine's import now take a CMYK (or CMY, or more inks) measurement of the run's chart. It is checked like an RGB one: the inks must be the chart's, more readings than the sheet carries is a different chart, fewer is a partial measurement, and every patch's device values must match the chart's patch with the same number. A CMYK measurement of another chart, an RGB measurement into a CMYK run and a CMYK measurement into an RGB run are refused with a reason that names both. i1Profiler `.mxf`/`.cxf` measurements of a CMYK chart convert too (they were RGB only). A calibration run still cannot import, as before.
- **"Was a strip read twice?"** (#182, ChromIQ's measuring engine, strip mode): each strip you read is compared with the strips already measured. When it looks very like one of them, ChromIQ asks, for example "Strip D looks very like strip C, which you already measured. Did you read strip C again?", with **Re-read strip D** and **Keep, it is strip D**. It compares only what you measured, never the chart's expected colours, and it asks only when the two readings match far more closely than the strip's own patches differ from each other, so strips of an ordered chart that merely look alike on matte paper do not set it off. Reading a strip again where the reader is never asks. The window plays the Instrument error sound. ArgyllCMS's own strip test stays off (-S) as before.
- **Calibrate during a measurement with K** (#182, ChromIQ's measuring engine, strip and patch by patch; Knut 5965478577, 5965735823, Basti 5965500670). Press K (k, K, or the K key on a Cyrillic layout) and the instrument takes a new calibration before the next strip or patch, without ending the measurement; afterwards the same strip or patch is offered again. Pressed during a swipe or while a question is open, it waits for the next strip or patch. Cancel calibration keeps measuring with the calibration you had. If a calibration fails, nothing more is read until one succeeds (an instrument can be left holding a bad reference after a failed calibration), and the window offers Try again or Save and stop. The placement window plays no sound. An optional **Calibrate** button can be switched on in Preferences ▸ Measurement (off by default); while a measurement runs it stands where the disabled Save as Defaults stands. K is on the keyboard help card, the printed card and every "Calibration complete" window. With ArgyllCMS chartread K does nothing (a log line says so; before, a typed k could start a strip read, or in patch-by-patch end the session without saving on a Cancel), and it is not available for the CR30 or whole-sheet readers.

### Changed

- **Rebuilding a profile moves only the profile** (#182, Knut 5964384250). "Build here anyway" no longer moves the run's dated verification measurements to "old"; they, their reports and the verification chart stay until you choose Verification and answer the window above. The rebuild warning is reworded: it no longer says each sheet "was printed through the profile", which is untrue for raw and FROM PROFILE GAMUT sheets.
- **Check & Refine: refinement is always offered** when at least one patch is above your limit (#182, Knut). The rule "more than three quarters of the strips, so start over", which told good 648-patch profiles to start over with no way to refine, is gone. Starting over is advised only when more than half of all patches are above your limit, and refinement stays available then too.
- **Check & Refine: two lists, worst first** (#182, Knut). "Re-measure these strips first" lists the strips with a patch that stands out clearly from the rest of the check (measured against that check's own spread, so it adapts to every printer) or that looks partly read as its neighbour, each with one sentence saying why; then the other strips above your limit, with their worst patch and how many patches are above. You choose "the strips listed first" (the default) or "all strips above your limit", and the guide goes through them in chart order.
- **One ΔE formula, named on every number** in the Check & Refine window and its report (ΔE00 by default), and no more strip averages. "Re-measuring the flagged strips can help" stays.
- **Patches a re-read already confirmed (yellow) are not offered again** by Check & Refine, and the window names them.
- **The saved Quality_Check report says what the window says**, the start-over note and the strip lists included.
- **Each ink's ramp starts its own strip on a calibration chart** (#182, approved by Knut). targen makes one paper white and then the ink ramps one after another, and they were laid out in that order, so a ramp ran on into the next strip: on a chart with 20 patches per strip the last magenta patch was the first yellow step, and the yellow strip ended on fill-up whites. Now every ramp starts a strip of its own with its own paper white; a ramp longer than a strip carries on to the next one, the next ramp still starts a fresh strip, and the rest of a ramp's last strip is paper white. printcal averages all the paper whites. With "Single Channel Steps" equal to the patches per strip (20 and 20, 27 and 27) the chart has exactly as many patches as before and no fill-up; with other strip lengths it can have a few more paper whites, and the estimate in Chart layout information counts them. For RGB, CMYK and any number of inks, with the ChromIQ layout engine and with printtarg. Only a calibration chart made by targen from "Single Channel Steps" alone is rearranged; profiling charts, loaded patch sets and a calibration chart with other patches added keep their order. Measured with ArgyllCMS (fakeread and printcal): the calibration is identical when the sheet has the same number of whites, and differs by at most 0.0008 when it has more, which is the extra whites' weight alone.
- **"Use as pre-conditioning profile" is described as what it does**: it spreads the new chart's patches evenly by how colours look on your printer and paper; it does not aim them at the colours that measured badly. The button keeps its violet colour, and the same correction is in the Profile Built window and the help of Create Chart's refinement profile.

### Fixed

- **Strip and patch patterns follow ArgyllCMS's rules, so every chart ChromIQ makes can be measured** (forum report; Knut, #182 5965589190). With the strip pattern "0-9" on a 14-strip chart, ChromIQ printed strips "10" to "14", which ArgyllCMS's pattern does not have, and both ArgyllCMS chartread and ChromIQ's engine stopped with "Bad location field value '(null)' on patch 266". ChromIQ now labels strips and patches exactly as ArgyllCMS's printtarg does, so letters or numbers can be used on either side (for example strips 1, 2, 3 with "0-9,@-9;1-99" and patches A, B, C with "A-Z"). A pattern that would make a chart the readers cannot read back (too few labels for the chart, or strip and patch labels that run together, such as numbers on both sides) turns its box red, the reason appears under the preview and Generate Chart stays unavailable until it is changed; nothing is built. The help beside both boxes now explains ArgyllCMS's rules with examples that work; the old help recommended "1-999" and "0-9", which ArgyllCMS reads as a single digit. Charts made with the default patterns are labelled exactly as before.
- **Sheets already printed with a pattern whose labels do not match** are read by ChromIQ's engine as printed, without changing the chart file. With ArgyllCMS chartread selected, the Measure tab says plainly that chartread cannot read such a sheet and starts nothing. A sheet no reader can measure is refused before anything starts. ChromIQ no longer switches to ArgyllCMS chartread after the engine stops on such a chart (it failed the same way), and the log names the real reason instead of "unknown error". Restore Used Chart redraws such a chart with the labels it was printed with.
- **Measuring no longer hangs at start on a Mac whose Bluetooth serial port does not answer.** Before it looks for an instrument, ArgyllCMS opens every serial port it can see, and on macOS 27 opening the Bluetooth port (`/dev/cu.Bluetooth-Incoming-Port`) could wait for ever, so the measuring engine, ArgyllCMS's own chartread and the other tools never started. ChromIQ now tells ArgyllCMS to skip that port for every tool it starts, whether "Faster instrument connection" is on or off. A value you set yourself in `ARGYLL_EXCLUDE_SERIAL_SCAN` is kept, and USB serial instruments are never skipped. Skipping the port only stops the search; with no instrument plugged in, that port is number 1 in ArgyllCMS's list and the measurement would still open it. So before Start Measurement or Read Single Patches starts a reader, ChromIQ now works out which port it would use, without opening anything, and when that port is the Bluetooth port it starts nothing and shows the "No Instrument Found" window at once. USB instruments, USB serial instruments and a SwatchMate Cube's own Bluetooth port are used as before.
- **A chart printed with a printer calibration can be profiled again after ChromIQ's measuring engine reads it.** For any chart made with a calibration (applied with `-K` or included with `-I`; RGB, CMY, CMYK or more inks; any instrument including the CR30), the engine wrote the calibration into the measurement as `nan` instead of numbers. For RGB, CMY and CMYK the profile build then failed with "Field 'CMYK_C' has unexpected type" (or 'RGB_R'); with more than four inks ArgyllCMS read the damaged calibration as zero for every ink, without an error. The cause was one line in the ArgyllCMS library code the engine is built from, on a path only ChromIQ uses; it is fixed, and the measurement now carries the same calibration as the chart. Measurements already written that way are repaired, see the next entry. Printing a verification chart through the profile of such a run now takes the calibration from the chart instead of the damaged measurement, and says so in the log.
- **Measurements with a damaged copy of the printer calibration are repaired, and build.** Before ChromIQ runs an ArgyllCMS tool on a measurement (Build Profile with colprof or the ChromIQ engine, Check & Refine and the other profile checks, averaging and merging reads, colverify, printcal, and resuming a measurement), it now checks the measurement's copy of the printer calibration against the chart. When the copy differs from the chart's and cannot be a real calibration (the `nan` above, or numbers outside 0 to 1, flat or not rising steadily), and the chart is provably the one that was measured (same calibration table shape, same device values for every patch), the copy is replaced with the chart's. A copy that is a real calibration but differs from the chart's, for example a measurement printed with another calibration, is never changed; ChromIQ only notes it in the log. Only that table changes: the readings and the file's date stay as they were, the file as it was is kept in the run's `old/<date-time>/` (a verification's in its date's `old/`), and patches confirmed by a re-read stay confirmed. ChromIQ says so once, in a window, and never while a measurement is running or over another window: a repair made when a measurement is resumed is shown once that measurement has ended. When no such chart can be found, the build-failed window now says that ChromIQ wrote the damaged table, instead of asking whether the file was edited by hand.
- **"Device Type" now shows what a preset's or loaded patch set really is** (forum report: CMYK, CR30). Picking a built-in preset (CR30, ColorMunki, i1Pro, Pharmacist, Knut, Scanner, Red River; every one is print RGB) left whatever Device Type was on the panel, so after choosing CMYK and then a preset the panel said CMYK beside RGB patches, Generate laid out the RGB patch set, and a CMYK calibration refused it with "set Device Type to CMYK" although it already said CMYK. Every preset, a loaded or attached patch set, a patch set applied from the editor and a run's own patch set when you select the run again now set Device Type from the patch set itself, and clear the add/remove-colorant rows. A patch set whose colours no Device Type makes is left as it is.
- **A preset's patch set that does not fit the printer calibration is refused before anything is built**, with a window that says how to get a chart for the calibration's inks: tick "Edit patch recipe (override preset)", set Device Type and press Generate Chart (or set the calibration to "None"). The preset stays selected, so that box is there to tick.
- **CMYK and multi-ink measurements in views that read RGB only.** The Measurement Report, its patch check, the automatic report after a measurement and the measurement details window said "No device RGB columns" or nothing at all for a CMYK measurement; they now say "This view supports RGB charts only for now" and that nothing is wrong with the measurement.
- **Replacing a measured printer calibration names the runs built on it again.** The question before a new calibration chart replaces a measured one is meant to list the profile runs built with that calibration. It read the runs' records the wrong way and always found none, so the list never appeared.
- **The Measure tab's pre-flight and "This chart already has a measurement" no longer open on top of another window.** They wait until it closes and then ask.
- **"Replace the stored chart" keeps the chart it replaces.** Measuring a different chart into a verification date that already had one copied the new chart over the old one in `<date>/chart/` and kept nothing, and left the old chart's extra files mixed in (a gamut chart's `-verify-reference.ti3` beside a regular chart made Restore Used Chart bring back a reference, so Print forced Raw). The old chart now goes to `<date>/old/<date-time>/chart/`, in the same folder as the date's old measurement once the new one is saved, and the new chart is stored on its own. If nothing is saved (Cancel on a later question, no instrument, a measurement that read nothing, an import the date refuses), the old chart is put back, because the date still holds the measurement made with it.
- **Charts record their creation date in English, as ArgyllCMS does.** Under another language the `CREATED` line of a gamut chart (and of charts laid out by ChromIQ, relaid charts, i1Profiler imports and exports, and colverify reference files) used that language's day and month names, for example "Fr. Okt. 02". Charts already written that way are still read correctly in every language ChromIQ ships.
- **Demo projects: verification dates come after the profile they verify.** They are history (Demo-Verify-History spans a year, so its trend graph reads as a drifting printer), but the generator builds the profile now, so every date was older than its profile. The demo profile is now dated back to before its first verification (ICC header date and file time); the dates stay where they were.
- **Check & Refine no longer loses a patch when a line of profcheck's output arrives in two pieces** (#182; Knut's run2 lost patch B26 that way).
- **Check & Refine in Manual mode uses the Manual panel's own limit**; it used the Guided panel's.
- **Run type Calibration no longer builds into a profile run** (#182, Knut). With a run whose chart came from a preset or a loaded patch set, Generate Chart in Calibration rebuilt that run's chart and moved its measurement and profile into the run's `old/` folder, without a window. In Calibration, Generate Chart now always makes the calibration chart with targen into the project's `cal` folder. Picking a built-in preset, "Load patch set" and applying a patch set from the editor say that they are not available for a calibration chart and change nothing, and the live preview does not re-lay a chart out while Calibration is selected.
- **A preset or patch set no longer follows you to another target** (#182, Knut). Switching to or from Calibration, to another run type or to another project drops it, and the "Edit patch recipe" and "Edit page layout" boxes start unticked on every target. Back on a run whose chart came from a patch set, that patch set is attached again and locked. A run whose chart was made by targen no longer keeps the previous run's patch set. A chart built from a preset or a loaded patch set into a New run or a new project keeps its patch set, and typing in the project name box changes nothing.
- **A calibration chart is printed in order** (#182): with the ChromIQ layout engine its ramps were shuffled over the sheet although "do not randomise" was on; they now run strip by strip in order. A CMYK calibration chart was also marked as shuffled (`RANDOM_START`) after it was built, because its four ramps are easy to tell apart; a calibration chart now keeps its in-order mark.
- **A calibration chart made with printtarg is printed in order too** (#182). With "Use the ChromIQ layout engine" unticked, Run type Calibration took "Randomise" from the layout settings and unticked "Preserve patch order", so printtarg shuffled the calibration chart, and its ink ramps could not be given a strip each. In Calibration printtarg now always keeps the patch order, and the ramps start their own strips as they do with the layout engine. Profiling charts still follow "Randomise" and "Preserve patch order".
- **The "Calibrate my printer" help card** says how the calibration chart is made (by targen, from "Single Channel Steps", so the Patch Set Editor is not needed) and that Generate Chart there writes only into the project's "cal" folder.
- **The log no longer calls a Generate on a loaded patch set a "live preview"**.


## v4.3.3-beta.6

**Continue to next or jump to unread; yellow outlines learned per colour range; progress that counts each patch once; and a Check & Refine window that shows every line.**

### New

- **Continue to next or jump to unread** (#182, ChromIQ's measuring engine): when you read a strip or patch again while others are still unread, ChromIQ asks once per measurement whether the reader should go on to the next one or jump to the closest unread one, and keeps your answer until the measurement ends. The window plays the Instrument error sound to get your attention. Your own moves (f, b, n, a click on the preview) always win, and a chart with nothing unread behaves as before.

### Changed

- **A red patch turns yellow by itself only from confirmed patches of its own colour range** (#182). There are 13 ranges: greys (dark, mid, light) and ten hue ranges from pink/rose to magenta. On an RGB chart, including one made from a profile, a patch's range comes from the chart's RGB numbers for it, read as sRGB (as ArgyllCMS targen estimates them without a profile), so the ranges mean the same on every printer; blue reaches to hue 315°, so the most saturated blues are not split between blue and purple. On other charts (CMYK, grey, more channels) the range comes from the patch's expected colour against the chart's own white. A range learns once three of its patches, at least ΔE 6 apart, were each read again and gave the same colour; then its other red patches that are off the same way turn yellow, earlier ones included, and they turn red again if the range loses a confirmation. A patch you confirmed stays yellow either way. The hover card shows the patch's range, and on a red patch how many of the three it has.

### Fixed

- **Re-reading patches no longer raises the measurement progress** (#182). A resumed measurement counted a re-read patch a second time, so the header could show 100 % while patches were still unread; progress now counts each patch of the chart once.
- **Check & Refine: the start-over verdict is translated and reaches the saved report** (#182). The reason sentence is translated, and the saved Quality_Check report now carries the start-over verdict and its reason, the worst patches, and translated headings, as the window does. The grade text keeps "Re-measuring the flagged strips can help" (Knut).
- **The Check & Refine result window shows every line** (#182): the strip and patch lists are no longer cut off after two lines, the flagged strips wrap into rows instead of running off the right edge, the last sentence is no longer clipped, and in German the buttons no longer overlap when the window is made narrow. This was already so in earlier versions.
- **Guided refinement says the order it really uses**: the strips are visited in chart order, not "worst ΔE first" (#182).
- **The log tells the truth about resuming a dated verification** (#182): it no longer says there is nothing to resume from just before the verification is resumed.
- **A profile build is now in the log** (#182): the ChromIQ engine writes every build setting and the result (fit, grid sizes, time taken), and a colprof build says how it ended.

## v4.3.3-beta.5

**Two flag limits and a yellow outline for patches confirmed by a re-read; outlines that stay after the measurement; and printer calibration with Apply & Embed (-K) done the way ArgyllCMS does it.**

### New

- **Two limits for flagging a patch**, in Preferences ▸ Measurement: one for charts whose expected colours are estimated (default ΔE 95, the limit ArgyllCMS's own chartread uses) and one for charts made from a profile (default ΔE 30). The chart decides which applies. A limit you had changed yourself is kept (#182).
- **Yellow outline:** a red patch that you read again and that gives the same colour is outlined in yellow: a real difference your printer and paper cannot reach, not a misread. Later patches of a similar colour with the same kind of difference turn yellow by themselves. The hover card says which (#182).
- **The confirmed patches are remembered** with the measurement and come back when you continue or refine it (#182).

### Changed

- **Restore Used Chart keeps the chart it replaces** in the run's `old/` folder (page images apart, which are made again when needed); before, it was discarded. The run's `.cht` is no longer stored with the chart, is kept on restore when it matches the restored chart and otherwise moves to `old/` together with its `.cie`. The window says what happens (#182).
- **A calibration must be for the chart's inks** for both Apply & Embed (-K) and Embed (-I), as in printtarg; a mismatch now opens a window that says how to fix it (for example, set Device Type to CMYK) instead of a line in the log (#182).
- The hover card leaves a blank line between its sentences (#182).

### Fixed

- **Apply & Embed (-K) with ChromIQ's layout engine applied the calibration twice.** The engine wrote the calibrated values into the chart file as well as onto the printed page; the profile then described the printer without the calibration, and Apply Calibration added it a second time (about ΔE 21–27 off in a model printer). The chart file now keeps the uncalibrated values, as printtarg does. A run made with an earlier version is detected, and Apply Calibration and Check & Refine warn before using it (#182).
- **Verification printing of a run printed with -K** now goes through the profile and the run's own calibration (in a model printer from ΔE 33 to 1.5). A verification chart that was itself made with -K is not printed through the profile, and printing raw without the calibration asks first. Every chart now records how its calibration was used (#182).
- **The red and yellow outlines no longer disappear when a measurement ends.** The redrawn preview used a different colour-difference formula (ΔE2000) than the live one (ΔE*ab), so a patch at 103 became 16 (#182).
- **Restore Used Chart never loses a file** when something fails halfway, and on a calibration the replaced chart goes into `cal/old/<date>/chart/`.

## v4.3.3-beta.4

**A fix for a crash when building a profile with ChromIQ's own profile engine on Apple Silicon.**

### Fixed

- **Build Profile no longer crashes** with ChromIQ's own profile engine when the perceptual and saturation tables are built from a gamut source (#182). Since beta 1 the Apple Silicon download uses a maths library (OpenBLAS) that needs more working memory on a background thread than macOS gives one by default; every background thread now gets enough.
- **"Stored chart differs" no longer appears for a chart that did not change** (#182). With "Save scanner files" on, every quality check rewrites the measured values inside the chart's `.cht`, and the comparison counted them as a change to the chart. The comparison, the Restore Used Chart button and the verification check now ignore those measured values; patch positions still count.
- **After reading a strip of a chart that was already complete, the reader moves on to the next strip** (#182), and the arrows above and below the preview follow. It stayed on the strip just read, the way ArgyllCMS's chartread does. A question window that asks to read the strip again still keeps it there.
- **A red outline on a patch is called "a large difference"**: either a misread, or a colour your printer and paper cannot reach. If reading the strip again gives the same value, it is real and belongs in the profile. Both help texts in Live preview explain this (#182).

## v4.3.3-beta.3

**Everything Knut found in beta 2: dated verifications offer their own measurement again, a saved report keeps the numbers it was saved with, and the measuring windows explain the beep and the red outlines.**

### Changed

- **A saved Measurement Report shows its "covers n of the total measurements" sentence as it was saved** (Knut, #182). Deleting or duplicating runs no longer changes it; pressing Update counts again. A report saved by an earlier version keeps counting live until it is updated once.
- **"Where are my files?"** names the files that Inspect a measurement and Inspect a profile save, and where they go, and says that outside a ChromIQ project Check & Refine and the two Verify tools save beside the measurement.

### Fixed

- **Choosing a dated verification that has a measurement** shows "Refine / resume" and "Show overlay" again, and refining it works: the new readings go back into that date. Switching Run type to Profiling no longer shows "The chart has not been measured yet" about the verification you just left (#182).
- **"Measure anyway" on a measured dated verification keeps the earlier measurement** in that date's `old/` folder, as the window promises. It was overwritten.
- **Verify against reference no longer leaves a reference file beside a run's measurement.** That file has the name ChromIQ reads as the chart's own colour reference, so the run's Measurement Report then judged against the typed-in values.
- **Start sliding at the beep, said everywhere it matters** (#202): the Calibration Complete window for the i1Pro family and the ColorMunki, Preferences ▸ Measurement (which now names every strip reader), and the measuring steps of the Welcome cards and the Getting Started tour. Every strip reader is timed from its beep.
- **Strip Read Quickly** names the same strip time as the line under the preview: 27 patches at 120 ms read "3.3 s" in both (#202).
- **A patch outlined in red says why** on the hover card, with its ΔE*ab beside your limit from Preferences ▸ Measurement, and the help for "Show patch values on hover" explains the outline (#202).
- **Report Results**: each date heading sits centred over its PASS, FAIL or INFO (#182).
- Ukrainian file paths keep the real folder name `reports/`.

## v4.3.3-beta.2

**A chart built twice from the same seed now comes out the same on a Mac, and a handful of smaller fixes from the review of beta 1.**

### Fixed

- **The same chart every time on macOS.** ArgyllCMS's printtarg reads a value it never sets when it lays out patches for a strip-reading instrument (ColorMunki, i1Pro and others), so two builds with the same seed could place the patches differently, depending on what happened to be in memory. On a Mac, ChromIQ now starts printtarg so that this memory is always empty, which gives Argyll's intended layout every time: in Create Chart, in the presets window and in the demo projects. Windows and Linux are unchanged.
- **Inspect a measurement and Inspect a profile** never offer a folder you cannot save into, such as a profile inside a printer driver or a project on a read-only disk: the save window opens in your ChromIQ folder instead. Their button now reads "Save inspection…".
- **The Verify tools** say "Report saved beside your measurement" for a measurement outside a ChromIQ project, where the report really goes, instead of naming a reports folder.
- **A question closed without an answer never prints or builds.** "Stuck Print Jobs Detected" and the two "Scan doesn't match the chart" questions took a window closed without a click as "go ahead". Your Escape key was always safe; now every other way a window can close is too.
- **Preferences ▸ Measurement** no longer changes the stored values of the locked SpectroScan and CR30 rows when you click OK.
- **A long message from the ChromIQ chart-reading engine** that arrived in two pieces was lost; it is now put back together.
- Clearer German in Preferences ▸ Measurement and for "Untersuchung der Messung".

## v4.3.3-beta.1

**The i1Pro 2, 3 and 3 Plus are judged by their own reading speed, timed from the beep; reports and inspections are saved where they belong; and ChromIQ runs again on older Macs.**

### New

- **A new i1Pro preset: "A4-324p-1page-Portrait-w15.0mm-Uniform 6x6x6-Full Page"**, made by Knut: the same 324 patches spread over the whole A4 page, so a small i1Pro chart can answer every row of "Which presets can be used for verification?". ChromIQ now has 189 built-in chart presets.

### Changed

- **Seven of Knut's presets use the near-neutral offset he set for them**: i1Pro A4-572p and Letter-572p (Uniform 7x7x7-Edge Emphasis), i1Pro Letter-162p, and i1Pro 3 Plus A4-462p, Letter-429p and A3-336p now have the offset 7 he chose for one ring of near-neutral greys, so their patch sets change; the i1Pro Letter-648p preset now opens its own design in the patch-set editor. A chart you already made from one of them keeps its patches.
- Two i1Pro presets have new names: "A4-162p-1page-Portrait-w7.5mm-Uniform 5x5x5-Quarter Page" and "A4-324p-1page-Portrait-w7.5mm-Uniform 6x6x6-Half Page". Whether you chose to show or hide them is kept.

### Fixed

- **Reading speed for the i1Pro 2, i1Pro 3 and i1Pro 3 Plus** (#202). These instruments were judged with the first-generation i1Pro's limit, so an i1Pro 2 was told to slow down to 240 ms per patch when 120 ms is enough. ChromIQ now recognises the name each instrument reports and uses its own row in Preferences ▸ Measurement. An i1Pro 3 Plus is also recognised as a Plus when the ChromIQ chart-reading engine is used.
- **A strip is timed from the beep** (#202), the moment the instrument starts reading, instead of from the button press: the lamp's warm-up of about 0.7 s before the beep no longer counts against your reading speed. The beep itself is unchanged. Preferences ▸ Measurement explains this, and the SpectroScan and CR30 rows there are locked, because these instruments do not read strips.
- **The speed hint never contradicts itself.** It could say "Too fast · 165 ms per patch ... Aim for 165 ms or more"; the numbers are now rounded so they always sit on the right side of the limit.
- **A verification measurement writes its automatic report** into its dated `reports` folder, as a profiling measurement already did, when "Save measurement report" is ticked. The Measurement Report window then opens on that saved report.
- **Generate report always asks** whether to update the report you selected or create a new one, also in the cases where it could write without asking.
- **"Save report as PDF…" is greyed** while the report area shows no report.
- **Duplicating a run** gives the new run its own copies of the run's reports. The copies used to point at the run they came from, so the new run listed them under "Reports including multiple runs".
- **Inspect a measurement and Inspect a profile** save as "Measurement inspection - <name> - <date and time>.txt" and "Profile inspection - …", named like the Measurement Report's files, into the `reports` folder of the run, dated verification, calibration or project the file belongs to. A file of the same name is kept in `reports/old/`, never overwritten. A file outside any ChromIQ project is saved directly beside it, and nothing else is created there. Check & Refine and the two Verify tools follow the same rule. A failed save no longer replaces the inspection with "Could not read this measurement".
- **The colour swatches in reports** have equal grey bars on both sides and the colour is twice as wide, so asked-for and measured colours are easier to compare, on screen and in the PDF.
- **Older Macs.** ChromIQ declares macOS 13 as its minimum, but 17 of its built-in programs needed macOS 14, among them the chart-reading engine. Every part now runs on macOS 13. Intel Macs from before 2010 (for example a 2009 Mac running Ventura through OpenCore Legacy Patcher) can run the universal and Intel downloads again: they keep numpy below version 2.4, which needs a newer processor. Thanks to RobFor for finding the cause (discussion #201).
- **A precaution for macOS 27.** On a Mac set to German, macOS 27.0 can close a program the moment it shows a system message window (an Apple bug). ChromIQ was not affected in testing, and now sets its number format so that it cannot be.

## v4.3.2

**A small fix release: two texts now say exactly what they should.**

### Fixed

- The "Chart layout" line printed down the right edge of a sheet names a built-in preset exactly as it is written in the preset list, with the instrument in front. It used to move the patch width and the name's tail to the end.
- The help for "Load setup from preset" in the New Patch Set window no longer says the "by Pharmacist" charts are missing from the list, or that the list stays empty until you save a preset. It now says that the built-in presets with a setup are listed, marked ★, and that a preset with a layout but no editor setup is not.
- In Create Chart ▸ Manual with printtarg, "Print info in left clip area" sits directly under "Stamp settings down the right edge".

## v4.3.1

**Five new "by Pharmacist" chart presets, made by Pharmacist and quality checked by Knut, take the place of the last four that came only as page images.**

### New

- Five "by Pharmacist" presets with a full page layout: the ColorMunki Ergonomical target on A3+ landscape (924 patches, 1 page), on A3 landscape (725 patches, 1 page) and on A4 portrait (624 patches, 2 pages), and the i1Pro Real World Target in standard quality on 4x6" photo paper (600 patches, 4 pages) and on 5x7" photo paper (702 patches, 3 pages). Thanks to Pharmacist for the charts and to Knut for checking them.
- Each of the five is a "Full layout setup": it builds with the ChromIQ layout engine, can be laid out again on another sheet, and brings its design for the patch-set editor. All five are shown in the preset lists straight away.

### Changed

- The last four "by Pharmacist" presets that came as pre-rendered page images are removed: the i1Pro 10x15cm 600 and 13x18cm 648 photo cards, the ColorMunki A3 924 TC9.24 and the ColorMunki A4 702 ABW-optimized. A project you already made from one of them keeps its chart and opens as before. ChromIQ now has 188 built-in chart presets.

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
- **Most i1Pro and i1Pro 3 Plus built-in presets have new names** that also say what their patch set holds, for example "A4-324p-1page-Portrait-w7.5mm-Uniform 6x6x6". Your ticks in "Settings for built-in presets" stay as they were.
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
- **"New Patch Set…" opens with the design of the preset chosen in Create Chart**, on that preset's own paper, not with the design of the last chart built.
- **An own preset renamed or copied outside ChromIQ keeps its patch set**, and a copy no longer disappears the next time you save.
- **Saving a preset no longer deletes another one** whose file name differs from its preset name only in upper and lower case, or in how an accented letter is stored.
- **Apply Calibration finds the project's calibration.**
- **A rare crash** when memory was cleaned up while a window was still receiving an event.
- **Translations**: every text is in all fourteen languages, each translation read a second time against the English, and labels that were cut off, or ran into each other, in some languages now fit.

### Known issues

- **Do not open a 4.3.0 project in ChromIQ 4.2.7.** 4.2.7 cannot tell that the project is newer, and saving it there drops the report settings this version keeps for its runs. If it has happened, set the run's "Default for this run" again in Edit limits.

## v4.2.7

**The output pane stops dragging you back to the bottom.** One fix, reported by
a user who was trying to read what had already scrolled past while a profile was
still building.

### Fixed

- **A log pane follows the tail only while you are already at the bottom.** Scroll
  up to read something and the next line of output no longer throws you back
  down; scroll to the bottom again and it resumes following. Nine panes across
  the app had the old behaviour, not one: Create Chart, Measure, Build Profile,
  Check and Refine, the spot-read window and the tool windows.

  Two further doors into the same panes needed their own fixes. The Create Chart
  tab collapses the patch-arranging output into one live percentage line and
  rewrites that line in place rather than appending, so it asked the "are you at
  the bottom?" question using the answer left by the last appended line: a reader
  who scrolled up after the percentage started ticking was thrown back down on
  every tick. And the line naming your instrument is replaced by removing it and
  adding the new one, so the question was asked of a log one line shorter than
  the one you were reading. A reader one line from the bottom was pulled down,
  and a reader at the bottom was thrown to the very top of the log. That last one
  has been there as long as the line has, on Build Profile and on Check and
  Refine, and nobody had reported it.

## v4.2.6

**A profile built from an i1Profiler measurement could record its paper white as
almost black, and nothing said so.** That fault has been on the stable line for
as long as the import has existed, and it is what this release is for. The rest
of it is the same road in: a complete measurement turned away as partial, a
measurement already sitting in a run that carried the fault in silence, an
export ChromIQ refused to read at all, and a chart in the project you have open
offered to you as another project's.

### Fixed

- **A profile built from an i1Profiler export recorded its paper white at
  lightness 8 instead of 95.** An i1Profiler CGATS export can write its XYZ
  columns on the 0 to 1 reflectance scale. ArgyllCMS's converter scales the
  device columns and the spectral columns and passes the colour columns
  straight through, so the converted measurement reached the profile builder a
  hundredfold too small. Relative colorimetric normalises the paper white away,
  so the profiles looked ordinary, while absolute colorimetric, paper
  simulation and every figure in the Measurement Report were wrong and nothing
  reported it. The scale is corrected on the way in now, using ArgyllCMS's own
  `spec2cie` rather than ChromIQ's arithmetic, so the numbers the profile
  builder is handed are the numbers it would have worked out for itself.

  **It decides by asking the file, not by the size of the numbers.** A chart
  made only of very dark patches has genuinely small colour numbers, and
  ChromIQ can generate exactly such a set, so a rule that rescaled anything
  small would destroy a correct measurement. The patch printed with no ink is
  the bare paper, and no printable medium is black: a file whose no ink patch is
  also its lightest and still reads almost black is on the wrong scale and can
  be nothing else. Where a file has no bare paper patch, the measured spectra
  are asked instead, and only when they can be trusted. A file that offers
  neither is left exactly as it is and nothing is said, because guessing can
  ruin a good measurement and saying nothing cannot. Every measurement file in
  the project, 426 of them, is byte for byte unchanged by this.

  **If you have a profile built from such a file, build it again, and import
  the measurement again first.** The correction happens on the way in, so
  re-importing the i1Profiler export is what produces a measurement with its
  colours on the right scale. Building again from the file already in the run
  folder would reproduce the fault exactly.

- **A measurement already in a run now says when its colours are on the wrong
  scale.** A file converted by an earlier version still carries the fault, and
  Build Profile used to arm its button and say nothing. The measurement line
  names it, and the Build button's tooltip explains what to do about it. Your
  file is not touched and the build is not forbidden: what it owes you is that
  it is not silent.

- **A complete measurement of a ChromIQ chart was refused as partial.** A
  printed sheet is filled to the end of its last strip, so a 400 colour chart
  is laid out as 414 patches. Two places counted those fill up rows as colours
  you were meant to measure. The Measure tab refused a complete import outright
  ("Nothing has been imported, measure again") and the Build Profile import
  filed it with "part of the chart was not measured". Both go through one
  counting rule now, and it knows the fill up rows of both layout engines.

- **An i1Profiler export of device values and spectral readings is read.** Such
  a file converts cleanly and comes out with no separate colour columns.
  ArgyllCMS builds a profile from it without complaint; ChromIQ asked for a
  colour column that was never going to be there and turned the file away.

- **A chart in the project you have open was announced as another project's.**
  The check compared the open project's folder as configured against the
  chart's folder as resolved, so the moment your ChromIQ folder was reached
  through a symlink the two spellings of one folder disagreed and the run's own
  chart was offered as a stranger's. No chart was ever lost to it; the question
  you were asked was the wrong one.

## v4.2.5

**Five things an audit of the beta-4 plan found on the stable line.** None of
them is report work; that is on the beta.

### Fixed

- **The Guided sheet takes its text-edge distance from Preferences, not from a
  number in the code.** Knut asked that the identification text stay within the
  default "Text distance from edge" setting in Preferences → Chart Layout, and
  not a hardwired margin. Guided mode and a printtarg chart carry no layout
  recipe, so three places read the built-in default directly. They ask for the
  preference now and fall back to the same number, so nothing moves today and a
  stored preference reaches every path the moment one exists.

- **A helper nobody called is gone.** Three more like it are recorded rather
  than removed, because one of them may be a dropped branch rather than dead
  code, and that is not a sweep's decision.

### Also

- The chart note is now checked at 150 dpi as well, the one resolution a report
  said it was dropped at. It is not dropped there, and has not been since the
  "the text is never dropped" ruling; the gap was in the test, not the sheet.

- The seed tick is checked where it is stored. Six tests covered the panel
  while the claim was about the run's own record on disk.

- Two design documents stopped asking a question that was answered on
  4 September: whether ChromIQ's measuring step accepts a CMYK chart. It does.
  The wall is at reporting, not at measuring.

## v4.2.4

### New

- **Auto align works on hexagonal charts.** Pressed on a honeycomb it used to
  decline and move nothing, while the same button placed a rectangular chart of
  the same 648 colours to within 0.6 px. Only the first of its three stages was
  at fault: it borrows scanin's recogniser, which hunts the straight horizontal
  patch edges a grid of rectangles has and a honeycomb does not. ChromIQ now
  finds the ink instead of the patch shape, so a honeycomb is no harder for it
  than a chequerboard. Measured over eight charts and 98 pictures, each page
  clean, turned 2 degrees, turned 12, noisy, on a dark cluttered bed, as an
  off-square photograph and with an edge cut off: 63 of 66 land within a quarter
  of a patch, and 20 of 22 pictures with the chart cut off are correctly
  refused. Rectangular charts cannot reach the new code and were measured
  unchanged, 64 placements out of 64.

### Faster

- **The patch set generator no longer rebuilds a set it already has.** Opening
  the generator with nothing changed rebuilt the identical patches, and the
  window ran the builder eight times doing it. At a 4000-patch fill that was
  48 seconds; it is now under half a second, and pressing Create drops from 12.4
  to 0.21. Change a setting and it still rebuilds, as it must.

- **And the first build is about four times faster, patch for patch identical.**
  9.0 seconds to 2.3 at 4000 patches. This decides which colours end up on your
  chart, so it was checked rather than assumed: 900 combinations of starting
  patches, totals, seeds, candidate counts and relaxation settings, plus the
  N-channel path at four to twelve channels. Worst difference across all of
  them: zero.

### Fixed

- **Hexagonal patches were drawn a third too wide.** In "Prioritise chart area,
  then fit patches to it", in both calculation methods, the hexagon came out
  4/3 wider than tall instead of regular, which is the flattened look Knut
  Larsson reported. "Prioritise patch size" was always right and is untouched.
  Worth knowing before it surprises you: at the same typed minimum width a
  honeycomb now fits about three quarters as many patches, because each patch is
  genuinely taller than it was.

- **The patch count over the preview told the truth about what will be built.**
  With a patch set attached the build never consults the Pages box, but the
  headline still multiplied patches per sheet by pages. On Knut's own test
  project, Pages 1 said 396 over one page and built 648 over two. Both numbers
  now read what is actually written. The same count is also refreshed the moment
  a patch set is loaded, instead of showing the previous chart's total until
  something else happened to nudge it.

- **The estimate describes the chart Generate will build.** With "Auto patch
  count" unticked it described the chart already in the preview, so it was
  always one build behind: it promised 525 and built 418, then promised 425 on
  one page while the build made 900 on two. It also never passed the count to
  the area-first layout, which sizes the patches from it.

- **The layout controls no longer jump when you change the calculation method.**
  The Calculation-method box moved 157 px and lost 157 px of width, which is why
  it read "By colum…". Nothing moves now, in any of the thirteen languages.

- **Labels in the Layout section are no longer cut off.** "Minimum patch width
  (mm):" lost the top of its first line. Across thirteen languages and both
  calculation methods there were five clipped labels before this release and
  there are none now.

- **Auto align says something true when it cannot find a honeycomb.** It used to
  tell you to drag the corners roughly round the chart and press again, which
  narrows a search that would find nothing however narrow it is.

- **A custom paper size is named by its size again, and carries Portrait or
  Landscape.** Saving a preset on a custom sheet produced a name containing
  `__custom__`, which is ChromIQ's internal marker and not a size. It now reads
  the size, so `i1Pro-100x150-600p-4pages-Portrait`. The orientation is worked
  out from the two numbers on Knut Larsson's ruling: narrower than it is tall is
  Portrait, wider is Landscape. A square sheet gets neither word, because it is
  neither. The help icon in that window explains it.

- **"Use a fixed seed" is remembered as you left it, and a chart reopens as it
  was printed.** Turning the tick off and coming back to the run turned it on
  again by itself. Worse, once it had done that, every Generate reused the same
  seed for ever, so "Randomise patch order" quietly stopped randomising. ChromIQ
  now stores whether the tick was on alongside the seed it used. Reopening a
  chart restores it exactly, from the stored seed, whether the tick is on or
  off, because looking at a chart you already made is not the same as making a
  new one. Generating after a change uses the stored seed only when the tick is
  on; with it off you get a new one each time, as you should. Charts built
  before this release have no such record, so their tick still reads as on.

- **Text along any edge of a chart is never left off again, and a collision is
  now shown on screen.** 4.2.3 left the small note down the right edge off the
  sheet when the margin was too narrow to keep the distance you had set, and
  said so only in the log. Knut Larsson's ruling reverses that: the text must
  stay visible, because otherwise you cannot tell anything is wrong. So the note
  is printed at the distance you set even when the patches reach it, and it
  prints over them if it must. The 10 x 15 cm photo card gets its identification
  line back.
- **…and the "Measured from Preview" frame says so, in red.** Whenever text runs
  into the patch area, its message field names the edge, the room the text needs,
  the room the margin leaves, and the two boxes that would fix it. It covers all
  four edges the same way: the strip letters across the top, the chart notes and
  the stamped settings down the right, the clip border content on either side,
  and the sheet text along the bottom. A chart with room to spare says nothing.
- **The warning for the strip letters and the sheet text is visible again.** It
  had been correct since 4.0, but on 2026-09-04 it moved off the panel onto its
  information icon along with the panel's explanatory notes, and an icon is only
  read if you hover it.
## v4.2.3

**Checking for updates works again on a busy network, the two photo-card charts
Knut asked for are in the Presets list, and a rule that was supposed to keep em
dashes out of the app could not see the dropdowns.** Nothing here touches the
Measurement Report; that work rides on the 4.3.0 betas.

### New

- **Two more i1Pro chart presets, for 10 x 15 cm and 13 x 18 cm photo cards.**
  Knut Larsson built them and widened the margins so there is room to start and
  finish a strip reading, which makes them slightly different from the
  Pharmacist cards of the same sizes. Both sets are offered; his are built by
  the ChromIQ layout engine and appear in the i1Pro group of the Presets
  dropdown beside the others. On the sheet they measure 7.49 mm patches over
  four pages and 8.00 mm patches over three.

### Fixed

- **"Check for Updates" said "GitHub answered 403" and gave up.** Nothing was
  wrong with ChromIQ's request. GitHub answers a limited number of update
  checks an hour to a caller with no account, and counts them against the
  internet connection rather than the person, so an office, a school, a
  household or a mobile network shares them. ChromIQ now falls back to a route
  that has no such limit, so the check simply works. When both routes are shut
  it says so in plain words, with the time it frees and a link to the releases
  page, instead of showing a number.
- **The same message was cut off, and in German the link was missing.** The
  line it is written into was pinned to a single line of text. It now wraps.
- **A second check while you were waiting forgot when the limit frees**, and
  fell back to "try again later". It remembers.
- **With no network at all the check showed the operating system's own error
  text**, untranslated. It now says that ChromIQ could not reach GitHub.
- **The note down the right of a chart ignored "Text distance from edge".**
  The setting was applied to the top and the bottom of the sheet and never
  sideways, where a fixed half a millimetre took over instead, so the text ran
  almost to the paper edge whatever you had asked for. Knut Larsson found it on
  a 13 x 18 cm card set to 4 mm, where the note ended 1.98 mm from the edge. It
  now keeps the distance you set, on the right as well: the same card now ends
  at 4.06 mm, and changing the setting actually moves the note, which it never
  did before.
- **Creating a new run gave it another run's settings.** Choosing New run does
  not copy the settings of the run you are standing on. It copies a cached
  block, and that block usually holds a different run's settings, because it is
  written only if it does not already exist and in practice it lands during the
  following build. So the block a run carried was the run before it. Knut
  Larsson reported the result: stand on a run, choose New run, press Generate,
  and the chart is not the same one. Measured on the files, the instrument
  changed, patches per strip went from 28 to 15 and one page became two. The
  panel moved the moment New run was chosen, before Generate was pressed. Now
  the live screen is written into the block first, which is what the design
  said all along. Starting from the first run of a project was always safe,
  because that is the only run whose block is its own.
- **And each run records its own settings again.** Of four runs, one recorded
  its own instrument before this and four do now. That is the half of his
  report that really did get worse after 4.1.4.
- **A note could print at 300 dpi and vanish at 200 on the same chart.** The
  distance from the paper edge is a measurement in millimetres, but the guard
  that keeps the note off the patches was counted in pixels, so the amount of
  paper it needed depended on how finely the sheet was rastered: 3.21 mm at
  150 dpi against 0.81 mm at 600. The guard is now a distance on paper too, so
  a chart with room to spare behaves the same at 200, 300, 400, 600 and 720 dpi.
  Right at the boundary it still does not: a legible line needs a minimum number
  of PIXELS, so a margin with about a millimetre to spare can still print at
  300 dpi and not at 200. Of fifty-one right margins measured between 4 and
  9 mm, eight sit in that band.
- **The same note also sat three millimetres away from the patches** and was
  centred in a strip wider than itself. It is now placed against the patch
  block, which is where there is room for it, and the line comes out larger and
  easier to read as a result.
- **Where the margin is too narrow to keep that distance, the note is left
  off.** That is deliberate, and it is Knut's ruling: the distance you set is
  kept whatever else has to give, and the remedy is to widen the margin. Of
  twenty-two chart settings measured, eighteen still print a note and the four
  that do not were all printing inside the distance they had been told to keep
  clear. One of the two new photo-card presets is affected: the 10 x 15 cm card
  has a 5 mm right margin, and once 4 mm of that is kept clear there is not
  enough left for a legible line, so its sheets no longer carry the small
  identification text down the right edge. Earlier versions printed it 0.76 mm
  from the paper edge, which is what the rule now forbids. The 13 x 18 cm card,
  with 7 mm, still prints it. Widening that margin is the remedy and it is the
  chart author's call. ChromIQ writes the reason into the log; it does not yet
  say so on screen, which is still to come. That count was measured at one
  resolution and
  it does depend on the resolution, because a very coarse raster has too few
  pixels to draw a legible line in the room that is left.
- **The rule that keeps em dashes out of ChromIQ's text could not see the
  Create Chart dropdowns.** It gathered a key that does not exist in the
  parameter file and missed the two that do, so 145 strings were invisible to
  it and 23 dropdown entries had slipped through. Those now read with a colon,
  and the rule can see them.

## v4.2.2

**A run's own settings stopped being rewritten every time you looked at it, and
the notes you type for a chart now reach the paper.** Knut Larsson found both in
one session. Selecting a run quietly replaced its stored settings with the ones
its printed chart had used, so a seed, a paper size or your choice of layout
engine could change without you touching anything, and deleting a run wrote that
run's screen into the run beside it. Separately, a long note on a chart ran off
the edge of the sheet, ignored the distance from the edge you had set, erased
any ruler markers it crossed, and on some charts was not printed at all. The CR30
honeycomb that 4.2.1 learned to turn is now turned in Guided as well, so every
user gets strips that run straight down the page.

### New

- **Guided turns the CR30 honeycomb.** A hexagonal chart built in Guided now
  stands its patches on a flat side instead of a point, the same option Manual
  offers in Expert Options. Every strip runs straight down the page instead of
  zigzagging, which is what you follow with a ruler while you read: measured on
  the printed sheet, the side-to-side wander within one strip goes from 6.01 mm
  to none at all, at the same patch size and the same ink. Manual keeps its own
  tick and is untouched. Guided also gives the CR30 a 5 mm margin where the
  other instruments use 6 mm, because a margin is the room an instrument needs
  to start and finish a strip and the CR30 is placed on one patch at a time. On
  A4 portrait that is 396 patches a sheet instead of 374.

  **A chart you built in Manual still rebuilds exactly as it was**, because
  Manual keeps the layout the chart was made with. A chart you built in GUIDED
  is rebuilt from the Guided settings instead, so rebuilding one you made before
  this release gives you the turned version rather than the sheet you printed.
  The panel warns you before you press anything: it shows the count of the chart
  on screen beside the count your settings would now produce, and marks them
  when they differ.

### Fixed

- **A run's settings were rewritten by the act of selecting it.** Choosing a run
  put its own stored settings on screen and then replaced them with the settings
  its printed chart had used, and filed those as though you had chosen them.
  Measured with nobody touching anything: a run's stored seed changed from none
  to a fixed number, and its stored paper size changed from one custom size to
  another. Your run's own settings now stay yours.
- **A run whose chart was made by the older tool lost its choice of layout
  engine.** The same fault, on one setting that was never protected: if a run's
  chart had been laid out by printtarg, the tick for "Use the ChromIQ layout
  engine" was cleared and filed as cleared, every time you selected that run.
- **A run with nothing saved yet borrowed the previous run's layout engine
  setting.** A brand new run now starts from your saved default, never from
  whichever run you happened to be looking at.
- **Deleting a run wrote the deleted run's settings into the run beside it.**
  Two runs, one set up for 111 patches and one for 648: deleting the second left
  the first asking for 648. Settings now follow their own run, and nothing is
  filed for a run that no longer exists.
- **Closing a project kept the run description and the chart notes on screen,
  and said the project had been deleted.** Both fields are cleared with the
  rest, and closing now says plainly that nothing was deleted and everything is
  still on disk. Deleting still says it was deleted.
- **A long chart note ran off the sheet.** The text was set to a size chosen
  from the width of the margin alone and then centred, so anything too long lost
  its END, which is usually where the useful part is. On a 13 x 18 cm card 4.2 mm
  of it was missing and on a 10 x 15 cm card 34.2 mm. The note is now made to fit.
- **The chart note ignored "Text distance from edge".** It started half a
  millimetre from the paper whatever that box said. It now respects it.
- **The chart note erased the ruler markers it crossed.** Not covered them: the
  note was written as a solid white strip over the finished page, so any marker
  dash inside it was gone. On one sheet a hundred pixels of marker were
  destroyed. The note is now laid over the page without rubbing anything out.
- **On some charts the note was not printed at all, and nothing said so.** With
  the side ruler markers switched on, or with the clip border on the right, there
  was no clear space left for the note and it was silently dropped from every
  page. It now knows to leave those marks alone and prints beside them, and it
  keeps off your own clip text rather than sharing the room with it: on twenty
  clip settings the note lands exactly where 4.2.0 put it, with none of your
  lines under it and none of them rubbed out. On a very narrow clip band, 10 or
  14 mm with the fuller kinds of note, there is still no room and the note is
  still dropped without a word. That is unchanged from 4.2.0, and the missing
  word is on the list.
- **A preset saved the wrong patch-set design.** Saving a preset recorded the
  design from the run's last generated chart instead of the patch set you had
  loaded, so two presets made minutes apart could carry identical designs while
  their patch sets differed, and "Load setup from preset" then offered the same
  setup twice. It now records the patch set you actually have.

## v4.2.1

**Two ready-made charts for the paper sizes photo paper is actually sold in,
and a honeycomb that can now be turned so its strips run straight. Nelson Lau
designed a 600-patch target for a 10 x 15 cm card and a 648-patch one for
13 x 18 cm, both for the i1Pro, and ChromIQ had nothing for either size before
now. A CR30's hexagonal chart gains an option to stand its patches on a flat
side instead of a point, which makes every strip run straight down the page
instead of zigzagging; its spacer becomes a ring around each patch rather than
a bar between rows; and the ruler helper markers, which a honeycomb could not
have at all, are available on both. Along the way: a project built for a CR30
stopped reopening as a ColorMunki and slowly becoming one, Preferences stopped
telling CR30 owners their instrument reads at 100 Hz, a setting you chose
stopped being thrown away when you looked at another instrument, and the patch
count for an unusual sheet size stopped being five times too high.**

### New

- **Two photo-card charts, by Pharmacist.** Create Chart, Manual, at the top of
  the i1Pro group in the Presets list and in the star overlay: a 600-patch
  target on four 10 x 15 cm cards and a 648-patch one on three 13 x 18 cm
  cards. Picking one asks for a name and copies the finished chart into the
  run, the way the other nine "by Pharmacist" charts work, so no chart is
  generated and nothing has to be laid out. Both are packed denser than
  ArgyllCMS lays an i1Pro chart out, which is what fits 600 patches on four
  small cards where printtarg needs nine sheets, at its own defaults and at the
  ones ChromIQ starts an i1Pro with alike. Both print almost edge to edge, so
  the preset says what that means for your printer before you choose it.
- **A chart preset can now be laid out for a sheet size that is not in the
  paper list.** These two are the first that are. Unlocking "Edit page layout"
  shows the sheet the chart was made for as a custom size with its width and
  height filled in, instead of quietly saying A4.
- **Straight strips: the CR30 honeycomb can be turned 30 degrees.** Create
  Chart, Manual, Expert Options, Patches & spacers, and only while the
  instrument is a CR30 with Hexagon patches on. It is off unless you turn it
  on, and it is saved with the target and inside a preset like any other layout
  setting. The patches themselves do not change: it is the same hexagon, the
  same size, stood on a flat side instead of a point, so nothing is stretched
  and each patch holds the same ink. What changes is that every second patch in
  a strip no longer sits half a patch to the side, so a strip you read patch by
  patch runs straight down the page and a ruler lies along it. The strips and
  rows come out a different length, so the number of patches on a sheet can
  move a little, in either direction, and by how much depends on the paper as
  well as on your margins, patch size and spacer settings. Measured at the
  standard settings it is 26 patches more on A2 and 24 more on Legal, against 15
  fewer on Letter landscape and 14 fewer on A4. A chart that only just fitted on
  one sheet can therefore need a second one, so check before you print. Read it
  off the "Chart layout information" panel, which shows the count for the layout
  you actually have.
- **Ruler helper markers work on a hexagonal chart.** They were refused on any
  honeycomb, on the grounds that it has no straight rows to lay a ruler
  against. It has: a honeycomb's patch centres sit on straight lines, and on
  any page one of the two page axes is one of them. The comb that lines up is
  drawn and the other is greyed with the reason, and which is which follows the
  turn above. This reaches the SpectroScan's honeycomb too, which had no
  markers before either.
- **A honeycomb's spacer is drawn around each patch instead of between rows.**
  Switching Spacers on for a hexagonal chart used to paint a bar across the
  sheet between one row and the next, which covered three quarters of the point
  of every patch above it and pulled the diagonals apart into slivers of bare
  paper. It is now a ring around each patch, which separates all six of its
  neighbours instead of two, and each of the six sides takes its own colour
  against the patch it faces, so "Black & white" still means black and white.
  Two patches that touch share one spacer on the side that touches. Because the
  ring comes out of the patch's own area rather than out of the page, switching
  spacers on no longer costs you patches: a sheet that held 9 strips of 26 with
  them off still holds 9 strips of 26 with them on, where it used to drop to 23.
  **A hexagonal CR30 project rebuilt with spacers switched on will lay out
  differently from before** for that reason; rectangular charts and the
  SpectroScan are unaffected.

### Fixed

- **The Linux build had no languages in it, and neither Linux nor Windows had
  the bundled scanner targets.** ChromIQ ships thirteen languages and a set of
  ready-made scanner charts, and the packaging list that says which files go
  into a build had drifted apart between the three platforms: the macOS build
  carried both, the Windows one carried only the languages, and the Linux one
  carried neither. Nothing announced it. On Linux the language list in Settings
  simply offered English and nothing else, and on Linux and Windows the scanner
  targets that Scanner Profiling offers were not there to open. Both are in all
  three builds now, and a check keeps the three lists level so a file cannot go
  missing from one platform again without somebody saying why.
- **A project built for a CR30 came back as a ColorMunki, and then became
  one.** Opening it restored the Create Chart row for the instrument you built
  with, and then the layout panel loaded either the run's own stored layout or
  the one "Save as Defaults" had left behind, and that overwrote the
  instrument. Whatever was showing was then filed as the project's own answer
  the next time anything was written, so the wrong instrument stuck and
  supplied the next open. Projects already carrying the wrong instrument are
  not repaired: correct the instrument once in Create Chart and it stays.
- **A setting you chose was thrown away by looking at another instrument.**
  "No strip-length limit" and "Triple density" were silently unticked when an
  instrument that has no such option was selected, and the loss was written
  into the run. They now come back with the instrument they belong to. The
  "Double density" / "Hexagon patches" box, which is a different option on
  each instrument, keeps its own answer for each of them, so hexagons chosen
  for a CR30 can no longer arrive on a ColorMunki as the double density that
  needs the measuring rig.
- **Preferences said a CR30 takes 100 readings a second, "from its
  specification".** That was the i1Pro's figure, and a CR30 takes one reading
  each time you press its button. The row now says so, and its information
  button explains what the instrument really does and that nothing on that row
  affects how a CR30 is read.
- **The patch count for an unusual sheet size could be wildly wrong.** Asked
  how many patches fit on a sheet ChromIQ has no measurement for, it searched a
  range that started above the real answer, never found anything, and then
  reported the guess it had started from. It said 443 for a 10 x 15 cm card
  that holds 90, 443 for a 13 x 18 cm one that holds 169, and 443 for a
  6 x 9 cm wallet print that holds 16. It now searches from a single patch, so
  every sheet an instrument can lay a strip on gets a measured answer, and
  every paper ChromIQ already had a measurement for is unchanged to the patch.
  One case is still open and is a different problem: on a sheet too small to
  hold even one patch, ChromIQ still shows a number instead of saying the paper
  does not fit the instrument.

### Documentation

- The licensing notes now describe the eleven bundled "by Pharmacist" charts
  properly: they are Nelson Lau's own work, sent as finished files rather than
  generated from a recipe in this repository, and he is credited by name.

## v4.2.0

**ChromIQ can now measure a chart with a CR30, the first instrument it drives
itself instead of handing to ArgyllCMS. The scanner and camera window asks what
the profile is for and sets itself up for that job. There is a third appearance,
Neutral, for anyone who would rather the app did not use colour to say things.
And a long list of faults that had been shipping for months is gone: a
measurement lost when you quit, an under-exposed scan that built a bad profile
and then rated it best of the run, a Windows driver installer that had never
installed a driver, and a "Save As" in the patch editor that handed back a
different chart.**

Eleven betas, folded into one list. Everything below is measured against 4.1.4.

### New

- **ChromIQ measures a chart with a CR30.** It is a low-cost spectrophotometer
  with no ArgyllCMS support of any kind, so finding it, identifying it,
  calibrating it and reading a patch are all ChromIQ's own work, over USB and
  over Bluetooth. It calibrates the instrument for you, showing both steps as a
  picture with the current one marked, and offers the dark reference as a tick
  box because a CR30 has no black tile. It also says plainly what it cannot do:
  a white calibration cannot be checked by software, because the instrument
  reports the same value whatever is under the cap. Read single patches works
  with a CR30 too. The instrument was reverse engineered on real hardware, and
  the protocol notes, the captures and the experiments that turned out wrong are
  public at https://github.com/itsab1989/chromiq-cr30-research. Used so far on
  macOS over USB and over Bluetooth and on Windows on ARM over USB, each with a
  real instrument and a real chart, and over Bluetooth on Windows 11, where a
  user reported connecting, calibrating and measuring without trouble. Linux
  should work and nobody has tried it.
- **A magnet at the measuring opening can no longer spoil a reading in
  silence.** A magnet makes a CR30 take a white calibration instead of a
  measurement and hand back its stored white-tile value, which looks like an
  ordinary patch colour, and a laptop lid, a fridge door or the instrument's own
  cap will do it straight through a sheet of paper. ChromIQ learns your own
  instrument's tile value (one press with the cap on over USB, two over
  Bluetooth), files it against that instrument so a second CR30 never inherits
  the first one's, then refuses such a reading, stops the measurement and offers
  to recalibrate on the spot. Everything measured before that moment is already
  saved. Over Bluetooth there is no equivalent signal, so use the cable if you
  have it.
- **Space, or Enter, takes the reading**, once your instrument's tile is
  learned. That is not only convenience: pressing the instrument's own button
  moves it by about ten times its own measurement noise, 0.5 %R against
  0.05 %R, both measured, so keeping it still is measurably more accurate.
- **See where the instrument will sit.** A CR30's 33 mm body hides the patch the
  moment you lower it, so the measurement preview now draws that body to scale,
  dashed, on the patch you are being asked for: line it up on screen, note which
  neighbours it covers, and put the instrument down so those same neighbours are
  evenly covered. A second, much smaller circle appears only when there is a
  problem, the 4 mm measuring opening, shown when the patch is too small for it.
  Both figures come from the manufacturer's own specification.
- **A Bluetooth report, for when the instrument will not connect.** Tools ▸
  Instruments. It separates the three cases (your computer's Bluetooth sees
  nothing, something is offering the service a CR30 uses, ChromIQ's own search
  accepts it) and writes a file you can send. It never asks the instrument to
  measure or to calibrate.

- **Twenty ready-made CR30 charts, from Knut.** Ten on A4 and ten on US Letter,
  from 77 patches on one sheet to 1,260 across three, eight of them hexagonal so
  that more round patches fit the page. They sit in their own CR30 group in the
  Presets dropdown and in the built-in presets bubble. Picking one builds the
  chart straight away: the colours are fixed, and every layout setting can still
  be changed.

- **Neutral, a third appearance.** A designed greyscale scheme rather than Light
  with the colour turned down: one accent value, five-cell rules where the tab
  hues used to be, and every icon redrawn to read without colour. Choose it in
  Preferences beside Light and Dark, which are unchanged, checked view by view.
- **The scanner and camera window asks what the profile is for.** Three choices:
  an everyday scanner or camera profile, a profile so the scanner can stand in
  for a measuring instrument, and a printer profile measured with that scanner.
  Picking one sets the profile type, the quality and the white point handling to
  suit it, so the three settings that decide whether the profile is any good are
  not something to remember. They also follow the size of your target: under 100
  patches ChromIQ starts from shaper plus matrix at Medium quality with "Map
  chart white to white", at 100 and above from the XYZ table at High with "Scale
  white to a perfect white surface". Nothing is locked, settings you saved
  yourself are never moved, and the window says which setting differs rather
  than changing it back.
- **Auto align, in the scanner and camera window.** Press it and ChromIQ tries
  to place the grid on the chart's patches for you, turning it the right way up
  if the scan was made sideways. It is an addition, not a replacement: nothing
  runs until you press it, one press puts your corners back exactly, and when it
  is not confident it says so and moves nothing rather than guessing. It works
  on all 25 bundled targets. On photographs it is much weaker, and dragging the
  corners roughly around the chart first is what makes it work on a cluttered
  desk.
- **The scanner and camera window is two panels.** The preview and its controls
  moved to the right, so the twelve wheel-turns of scrolling it used to take to
  reach the last control are now none, and it fits a 1280 screen in the twelve
  languages it was measured in. The preview takes the space the window gives it
  instead of staying pinned at its minimum, and the six buttons under it are
  grouped by what each one acts on.
- **Windows: one place to get an instrument driver.** For ArgyllCMS's supported
  devices and for the CR30's USB bridge. ChromIQ checks what is bound, offers
  the right package, asks for consent before anything elevated happens, says
  what it changes on your machine before you click, and says what it did
  afterwards.
- **"Show row numbers", on any chart.** ChromIQ has always printed a number
  beside each row on a SpectroScan chart, which together with the letters along
  the top lets you find one patch among several hundred the way you find a
  square on a map. There is now a checkbox for it in the layout panel, next to
  "Show strip indicators", for every instrument. Every chart you have already
  made looks exactly as it did: the setting starts out as "whatever this
  instrument normally does". Switching it on reserves 7.5 mm down the left edge,
  which the patch estimate and the built chart both take into account.
- **Check & Refine is a proper import door.** Browse for a measurement that is
  not in one of your projects and ChromIQ asks where it belongs, in the same
  window Build Profile uses; it used to make a project without asking. A third
  answer, "Just check it where it is", copies nothing, makes no project and
  writes the report next to the file, and the window says what that costs you.
- **A profile keeps its accented name.** A profile called Müller-Prüfdruck used
  to arrive as M?ller-Pr?fdruck in Windows' colour management, because the ICC
  field ArgyllCMS fills cannot hold an accent. ChromIQ writes the name into the
  field that can, and reads it back in its own Profile Info window.
- **The ColorMunki's dial is drawn.** Both calibration windows show the wheel
  turned to the mark that window is asking for, so the two cannot be confused.

- **The scanner and camera help is written as steps, with the reasoning kept
  aside.** Both printable cards are built around the three scenarios: the steps
  are what to click, and the longer explanations sit under them as notes you can
  open if you want them. On paper every note is printed, because a sheet has
  nothing to click.

### Changed

- **The scanner's Profile type control no longer says something nothing
  measured.** Four hundred profile builds on two targets, scored only on patches
  the fit never saw, settled where each type wins: shaper plus matrix below
  about a hundred patches, a lookup table above it. The help says so and points
  at where you can read your own patch count. The Lab table clips anything
  lighter than the chart's own white, so the XYZ one is marked as the
  recommended lookup table.
- **The white point options say which profile types they suit** rather than one
  of them being called the default, because that default costs real accuracy on
  the two matrix types. "Restrict white, black and primaries" now shows as
  ticked when your white point choice includes it; the flag was always being
  sent and the box did not say so. What is stored stays your own value.
- **Every warning, information and question sign in the app is ChromIQ's own.**
  The platform's signs were still showing in 70 places across 13 files. All
  three are drawn for Light, Dark and Neutral, and Neutral stays hueless.
- **Explanation has left the Create Chart sections for the ⓘ it belongs to.**
  Four blocks of standing text now ride on the information icon of the control
  they describe, with the first line also in the hover tooltip. 246 px of
  vertical space returned in English, 262 in German, and the panel did not get
  wider in any language.
- **Patch size and Patch scale have moved into Basic**, next to "Prioritise
  patch size", where the help has always said they were.
- **The chart legend fades out when you point at it**, so you can see the
  patches underneath. On a chart whose patches run to the paper's edge it has to
  rest on the last row, and it now simply gets out of the way.
- **An unmeasured calibration chart is treated as an experiment.** Replace one
  and it is not kept, the way a profile run's chart is not kept; a calibration
  that has been measured is always archived to the project's "cal/old" folder.
  The window says which of the two is about to happen. Before this it promised
  to keep a chart and then deleted five files.
- **The scanner window checks that what it read is the chart you meant.** It
  compares the reference against the chart, the read against the reference, and
  looks for clipping, before it builds anything.
- **A preset no longer names your project after itself.** Loading a built-in
  preset with the name box empty used to name the project after the preset, so a
  folder, the name printed on the chart and the finished ICC could all end up
  called something like "i1Pro-A4-162p-1page-Portrait-w7.5mm". ChromIQ asks you
  for a name, in a window that takes the answer and builds the chart.
- **The bundled CMYK profile is no longer Adobe's.** ChromIQ was redistributing
  `USWebCoatedSWOP.icc`, which Adobe's licence does not permit. It is replaced
  by ArgyllCMS's public-domain equivalent.
- **Your log reaches about three times further back.** A debug line recorded
  every help icon the app built, around three fifths of everything ChromIQ
  wrote, and pushed the entries that diagnose real faults out of the file.
- **Return no longer presses the button that discards a chart**, and the Tools
  menu is capped and scrolls instead of growing past the bottom of smaller
  screens.

- **The profile Algorithm list is two entries, and both of them work.** It had
  eight. Five of them could never build a printer profile: ArgyllCMS builds a
  printer profile as a lookup table or not at all, and colprof refuses a gamma,
  shaper or matrix model for one before it has read a single measurement. A
  sixth, "XYZ cLUT + matrix", built a file identical to plain "XYZ cLUT",
  because the matrix it promised is thrown away for a printer. What is left is
  "Lab cLUT" and "XYZ cLUT". The gamma, shaper and matrix models are not gone
  from ChromIQ: they suit a scanner or a camera, and the scanner and camera
  window still offers them there, where they work.
- **Three of those entries also named the wrong algorithm.** colprof's own
  names are `s = shaper+matrix`, `G = single gamma+matrix` and
  `S = single shaper+matrix`; ChromIQ called them "Single gamma + matrix",
  "Gamma + matrix (forced)" and "Single gamma + matrix (forced)". "Single" in
  ArgyllCMS means one tone curve shared by all three colour channels, not
  "forced", and the entry ChromIQ labelled as a gamma model was the shaper one,
  which ArgyllCMS calls the better of the two. The scanner window's names were
  right all along.
- **If a project of yours was saved with one of the entries that has gone, it
  still opens, and ChromIQ tells you what it did.** "XYZ cLUT + matrix" becomes
  "XYZ cLUT", and the profile that builds is unchanged, because for a printer
  the two were the same file. Anything else becomes "Lab cLUT", with a line
  saying the stored setting could not build a printer profile at all. Nothing
  is changed behind your back and nothing is thrown away.
- **The scanner and camera window no longer offers "Shaper + matrix" or
  "Matrix only" while "Profile my printer from this scan" is ticked.** That
  tick makes it a printer profile, so the same ArgyllCMS rule applies. With the
  tick off, all four types are there as before.
- **Quality is no longer greyed out for the shaper and matrix profile types.**
  It was greyed out and then sent to ArgyllCMS anyway, so it was doing
  something you were told it did not do and could not change. It does apply:
  for a lookup table it sets the table's resolution, and for the shaper and
  matrix types it sets how finely the tone curves are fitted. Measured, it
  changes the profile for every type.
- **The twelve translations were read end to end, and the English was corrected
  where they found it wanting.** Translating a string means reading it, which
  is a review nobody else performs, and it turned up things no test could see.
  The CR30 patch instruction said *"Take the magnetic cap off the measuring end
  first, with the cap on, the CR30 reads its own white tile"*. Read past the
  second comma and "with the cap on" attaches to taking the cap off. Five more
  sentences ran two clauses together on a comma. A help card told you to tick
  "Also save scanner-profiling files" when the box says *for this chart* too,
  and another quoted "Sides" and "Top/bottom" for boxes that read *Sides
  (vertical)* and *Top/bottom (horizontal)*. One window was titled "Check the
  dark calibration" over a body about the dark reference, while the rest of the
  app calls that act a black calibration. The connection-lost line said
  `[WARN]` where the line under it says `[ERROR]`, and the app was evenly split
  between the two spellings. And "Unexpected Color
  Response" is now "Unexpected Colour Response", which is how the app spells
  colour everywhere else, including in the help card that quotes this window.
- **A help card no longer names a control in English in a window that renames
  it.** The folder guide tells you what printcal's "Re-calibrate" and "Verify"
  modes compare against, and ten of the twelve languages had left those two
  words in English, so a German reader was told to look for a control that
  reads *Nachkalibrieren* on screen. Four smaller cases went with it, and the
  log tag is now English in every language rather than translated in some
  strings and not others in the same log.

### Fixed

- **Tools ▸ Build profile with scanner or camera sits still when you press a
  radio.** Switching "Create profile using:" between a ChromIQ chart and a
  bought target resized the whole window, from whatever height you had dragged
  it to back to the height it opens at: 700 px became 936 in English and 952 in
  German. The same click also slid both of those radios 79 px down the column
  (94 in Russian), because the explanation of why the printer scenario is not
  offered for a bought target appeared above them. The explanation is still
  there, in full; it now appears below the radios, where it cannot push them,
  next to the option it tells you to choose instead.
- **The usage-scenario help is one line each, with the rest behind the ⓘ.**
  Three paragraphs under three radios took 150 px off the top of the left
  column. Every word of them is now behind the ⓘ beside "Usage scenario: what
  is this profile for?", and the three lines that stayed still say which
  scenario to pick and that the second one builds the profile the third one
  needs. The left column is 105 px shorter, and the window is narrower in five
  languages as well: German 709 px to 662, Italian 707 to 663, Dutch 681 to
  661, French 706 to 668, Spanish 697 to 679.
- **Opening the Advanced section no longer widens the window.** It never did
  before, but only by accident: the gloss paragraphs happened to be wide enough
  to absorb what the Advanced editor needs. With the glosses down to one line,
  five languages would have grown by up to 54 px on a disclosure. The pane is
  now sized for the section it will have to show, and is still narrower than it
  used to be in every language.
- **Two frames under the chart preview no longer touch the edges of the pane.**
  The "Measured from Preview" frame sat flush against the panel separator and
  "Chart layout information" flush against the right edge of the window. Both now
  keep a 16 px gap, which is the inset the rest of that tab already uses. The
  preview above them is unchanged.

- **A measurement is no longer lost when you quit.** Closing ChromIQ during a
  measurement killed the reader, and the reader only writes its file on a clean
  exit, so the reading was gone with no warning. Quitting now asks, the way
  every other way out of a session already did.
- **"Save and stop" saves.** It was sending the reader a key it rejects, so the
  session never ended and nothing was written. "Keep measuring" now keeps
  measuring instead of stranding the session.
- **A single corrupt byte in a measurement no longer destroys it.** One zeroed
  byte in a `.ti3` made ChromIQ read the whole file as a different encoding and
  replace it with nonsense.
- **The optional calibration window no longer closes ChromIQ**, and its "Skip
  this step" button now does something. Both faults appear only with an
  instrument that offers optional calibration, such as a SwatchMate Cube, and
  both took the measurement in progress with them.
- **Importing a measurement can no longer end the app.** Four separate causes: a
  folder ChromIQ cannot write to, a disk that is full, a drive or share that has
  gone away, and a project whose own `project.json` has been damaged. Each now
  says what went wrong and leaves everything as it was.
- **A measurement can no longer be filed into the wrong project.** Picking a
  folder whose name contains something like a space (a Finder duplicate, an
  unzipped hand-off, a Dropbox conflicted copy) used to make an empty project of
  a slightly different name and then complain that it had no chart in it. A
  project behind a symlink, on an external drive or on a NAS could take the
  measurement into whatever project happened to be open instead.
- **A measurement refused as not belonging to the chart no longer leaves a run
  behind**, under a window saying nothing had been changed. The same check now
  covers the other road into a run: choosing an existing run that happens to
  hold no chart used to accept anything at all, in silence.
- **A print that never happened is no longer recorded as one.** A sleeping
  printer or a cancelled dialog left a record saying the sheet had been printed
  through the profile, which then silently changed the yardstick every dE in the
  report was measured against. That record also travels with the chart when a
  run is duplicated; it used to be dropped, so the guard that asks whether the
  sheet was converted when it was printed stopped firing on the copy.
- **A measurement report that could not be saved said nothing at all**, while a
  report that saved announced itself, so the failure looked exactly like
  success. It now says so, and says first that the measurement itself is safe.
- **Saved measurement reports were re-graded by whatever the thresholds say
  today.** A report is a record of a judgement made on a day; it now keeps the
  thresholds it was judged with and the verdict it was given.
- **A refine-strips list is no longer overwritten in place.** It was written
  under one fixed name, so re-checking a run destroyed the list from the check
  before it. They are numbered now, like the quality reports beside them, and a
  file written by an older version is left exactly where it is.
- **The scanner and camera window opened on a pair its own dropdown calls
  wrong.** With nothing loaded yet, the everyday scenario was lit over Shaper +
  matrix and "Scale white to a perfect white surface", the entry marked "best
  for cLUT profiles"; only clicking another scenario and coming back put "Map
  chart white to white" under the matrix type. A fresh window now opens on the
  everyday settings for a small target and says so once in its log, a chart
  or target still refines all three from the patch count, Restore defaults
  restores that same pair, and a hand edit of the white point with nothing
  loaded is named in the note. Settings you saved with "Save as Defaults" are
  still never changed; a saved record that carries no white point entry at
  all, which a save on an untouched window used to write, is shown with the
  entry that pairs with the saved profile type until you save again. Reported
  by Knut on the first open of the window.
- **A run with no settings of its own opens on your saved defaults.**
  Selecting a run made before 4.1.5, or a run that was created without a
  chart, used to leave the previous run's instrument, paper, layout mode,
  indicator checkboxes, stamp option, Guided settings and gamut options on
  screen, and then store them as that run's own. Choosing "New run" in the run
  bar is unchanged: it still starts from the run you were on, so a new run is
  "like the last one, with one change".
- **An under-exposed scan built a profile with no warning, and the app rated it
  best of the run.** Measured at 21.7 dE out. The scan is now judged before it
  is trusted, and one too dark to profile from says so instead of producing a
  plausible, wrong profile.
- **A sheet photographed ten degrees off square was accepted as correctly
  placed.** Keystone is measured against a limit now rather than assumed away:
  328 correct placements separate cleanly from 106 wrong ones.
- **The alignment diagnostic drew no outline**, so a correct read looked
  misaligned; zooming it interpolated away the very edges being judged; and a
  refusal could not be diagnosed from the log. All three now say what happened.
- **A scan that is not the target you chose, an unreadable reference, and a
  scanin diagnostic image loaded as a scan** each said nothing, or blamed the
  wrong thing. Each now names what it found. The profile self-check also had no
  floor and no guard against a meaningless number.
- **The scanner white-point default clipped every original brighter than the
  chart's own board.** New scanner profiles start from a better default, and the
  help no longer says "1.00 makes no change", which is the opposite of what it
  does. Nothing in ChromIQ used to say that a scanner profile meant to stand in
  for a measuring instrument must be built for that purpose; it does now.
- **"Save As…" in the patch editor turned a chart ChromIQ had laid out into a
  different chart.** A change made in June switched the editor's ChromIQ layout
  engine off without anyone noticing, so the saved chart came back with extra
  fill patches, a different strip grid, and without the sidecar that records its
  layout, which the measuring path reads. Measured on a 525-patch i1Pro chart:
  525 patches became 528 and a 21 by 25 strip grid became 24 by 22. It now saves
  back identical, patch for patch and strip for strip. "Apply / Save ▸
  Overwrite" was never affected. If you kept a chart saved this way, save it
  again from the editor to get the layout back.
- **An i1Pro chart lost its automatic bidirectional reading whenever the project
  was reopened.** The instrument a chart names is written into the chart file by
  the layout stage, and after a reopen ChromIQ looked for it in the wrong file
  and found nothing, so the i1Pro family lost the setting that lets a strip be
  swiped either way, the preview's bidirectional arrow was wrong, and the pace
  row fell back to the i1Pro minimum sample count.
- **"Prioritise chart area" now honours your left margin.** The 7.5 mm band that
  carries the row numbers was reserved outside it in every mode, so a 1 mm
  margin put the first patch at 8.5 mm. It sits inside the margin now, in the
  one mode whose whole contract is that the patch area is exactly the margin
  box, and the panel warns when the margin is too tight for the numbers. The
  margin readout also says what it measures, "Left (to first patch)", and
  explains the two things that legitimately sit in that space.
- **A hexagonal patch was reported smaller than it prints.** The layout panel
  gave the row pitch as the patch height, so an 11.3 mm hexagon was listed as
  11.3 by 9.8 when it actually stands 13.1 mm from point to point. Hexagons
  interlock, so the pitch is real and useful, but it is not the patch: the panel
  now gives the patch size, and a separate "Row pitch (mm)" line for honeycombs.
  Nothing about the charts themselves changed, only what was reported.
- **On a hexagonal chart, two layout controls did nothing and did not say so.**
  With the strips pinned, neither "Patches per strip" nor "Minimum patch height
  (% of width)" could change the chart, because a honeycomb interlocks: its
  height follows from its width, and the strip count already decides the size.
  Both are locked where they cannot work, with the reason on the row's
  information button, and both stay live where they genuinely do something.
- **The seed box read 0 while the chart on screen had been built with something
  else.** With "randomise patch order" on and no fixed seed asked for, the
  engine drew its own seed and nothing carried it back to the box, and 0 is a
  valid seed rather than a placeholder, so the box was reporting a wrong answer
  as fact. The seed itself was never lost: it is written into the chart file,
  the chart's sidecar and the build log, and all three always agreed.
- **Row numbers fit the row they name.** On a tall chart the automatic size was
  taken from the patch width, so the numbers printed over each other into an
  unreadable ladder. They also stay inside the "Text distance to edge" limit
  instead of walking to the paper's edge on charts with more than ninety-nine
  rows.
- **A flagged patch keeps its whole red ring** on a hexagonal chart, where the
  neighbouring patch used to be painted over part of it; **loading a new chart
  no longer shows the previous chart's measurements**; and **the legend no
  longer lands at the top of the sheet**, over the column letters, on charts
  whose strip geometry is not recorded.
- **Windows: a project name that was accepted and then could not be written.**
  Names of about 111 to 120 characters passed the name box and then failed when
  ChromIQ wrote the chart, because Windows limits the whole path rather than
  each folder name. The limit is worked out from the longest file ChromIQ
  actually creates, and a project you already have opens whatever it is called.
  A name too long for the filesystem is now refused with an explanation instead
  of failing halfway and leaving a half-made project behind.
- **Two projects whose names differ only in capitals no longer overwrite each
  other's chart.** ChromIQ kept the name you typed while the folder kept its
  own, so one run could hold two charts, each invisible to the other.
- **A bracket in a project's folder name no longer hides its chart**, and an
  asterisk no longer lets one project claim another's files.
- **A project with an umlaut can be opened after a trip through a backup drive
  or a Windows machine.** Older Mac disks, and Windows, store accented names
  differently from a modern Mac, and ChromIQ used to find none of the project's
  files afterwards while telling you the chart was missing. On Windows it could
  be worse than invisible: a different chart was used in its place.
- **Everything ChromIQ writes now names its encoding**, so a file written on
  Windows and read on a Mac, or the reverse, arrives as what was written. This
  is GitHub issue #178.
- **On Windows, every measurement lost its own bookkeeping.** ChromIQ's
  measuring engine reports what it is doing as it goes, and a Windows chart path
  like `C:\Users\…` was written into that channel without escaping, so the
  message carrying the strip map and the patch count was thrown away silently,
  on every measurement. macOS and Linux were unaffected, because their paths
  have no backslashes.
- **Windows: the "Install USB Driver…" button had never installed a driver.**
  Not for any of the 28 supported instruments, not on any architecture, not
  once. It passed an option the tool it runs does not have, so that tool printed
  its usage text and exited cleanly, and ChromIQ read that as success and
  reported an installed driver every time, having installed nothing. It named no
  destination either, so anything it did extract went wherever the elevated
  process happened to start; and an instrument that still had a driver recorded
  against it from a different USB port made ChromIQ believe the device was ready
  and never offer to install anything at all. Found by testing that path against
  real hardware for the first time.
- **Windows: ArgyllCMS cannot use WinUSB, and ChromIQ told users to choose it in
  seven places.** An instrument bound to WinUSB is invisible to ArgyllCMS. The
  driver helper installs libusb-win32 now, and the Zadig instructions no longer
  point at the one driver that cannot work. If you followed the old advice, the
  helper puts it right: rebinding was tested on an X-Rite i1Studio, from
  `** No ports found **` back to a working instrument. ChromIQ also refuses
  outright to install WinUSB on a USB-serial instrument, whatever asks it to.
- **A project whose name ends in an underscore and digits silently lost its
  exports**, and **the ICC filename and the description embedded inside it
  disagreed** when no description was given.
- **A window can no longer open taller than your screen and take its buttons
  with it.** Long messages are widened rather than stretched, anything left over
  goes behind "Show Details", and no message window, tool window or patch editor
  can open past the edge of the usable screen. The patch editor opened 1280 by
  820 whatever screen it was on, which put Apply / Save… and Close under the
  bottom edge of a smaller laptop, and three controls in the scanner window
  opened past the bottom of the screen for the same underlying reason: a window
  was placed before it was sized, and nothing put it back.
- **The app no longer crashes when a tool window is opened** after a spot read
  ends badly, and a scroll bar that was crashing the app outright in some
  windows is fixed.
- **"Build anyway" was drawn as "uild anywa"** in three windows that built their
  own buttons and never called the helper that has fitted them since #130, and
  **four instruction labels were painted in the one colour that cannot carry a
  word**: 1.25:1 in Light and 1.02:1 in Dark, against the 4.5:1 that AA asks
  for. Now 13.6:1, 5.1:1 and 12.1:1.
- **Fourteen German sentences named buttons that do not exist**, including all
  three buttons of the window that decides whether your measurement is kept, and
  **four languages could not say where a measurement was running**: Italian,
  Portuguese, Polish and Russian glued a preposition to a translated label and
  produced ungrammatical text. Each language now supplies the whole sentence.
- **A chart whose paper size is larger than printtarg can lay out no longer
  answers with a wall of usage text.** The two custom paper boxes also offered
  sizes up to 9999 mm, and printtarg stops at 4000; both agree with the tool
  now, and the values ChromIQ sends are checked against what printtarg accepts
  before it is started at all. When a tool does refuse a chart, the patch editor
  says what happened in ChromIQ's own words and quotes the one line of the
  tool's answer that means something, instead of showing you the raw output.
- **Layout settings restored from a chart folder are range-checked**, not only
  checked for the right names, so a hand-edited or damaged `meta.json` cannot
  pass a value the tool refuses.

- **A profile build that ArgyllCMS refused for this reason produced no
  message.** It wrote no profile, opened no window and left one line in the
  log. It now says what happened and what to change. This is the same silence
  the beta 11 note described for a setting that never existed, and it was still
  there for five settings that do.
- **The "estimate" column described the chart you had before, not the one on
  screen.** Generating a chart, or picking a preset, left the estimate showing
  the previous chart's patch count and strip count, so loading two presets one
  after the other looked as though the two columns had swapped. Both columns now
  follow the chart in front of you. The charts themselves never changed.

### Documentation

- **`THIRD-PARTY-NOTICES.md` states the terms for everything ChromIQ ships**,
  measured per file rather than assumed. The bundled scanner targets are marked
  AGPLv3, matching ArgyllCMS, whose patch geometry they carry. No recognition
  file changed, and ChromIQ itself remains GPLv3.
- **`docs/cr30_platform_support.md` is the CR30 page**: what each platform
  needs, what has been tried on hardware and what has not. On Windows the
  instrument is reached through a serial driver, not WinUSB; macOS needs
  nothing; on Linux the driver is in the kernel and your user needs permission
  to open the serial port.

## v4.1.5-beta.11

**Opening Tools ▸ Edit / create chart patch set on a CR30 chart stopped the
window with fifty-one lines of ArgyllCMS usage text, in a box three hundred and
fifty pixels taller than the screen, with its only button off the bottom.** It
happened on every open, from either door, and there was nothing the user could
do inside that window to get past it.

Hunting that down turned up something quieter and worse: a line changed in June
had switched the patch editor's ChromIQ layout engine off without anyone
noticing, so "Save As" on a chart ChromIQ had laid out handed back a different
chart.

The rest of this release comes from a beta 10 review: the scanner and camera
window now asks what the profile is for and sets itself up for that job, and
three layout controls that quietly ignored what you typed on a hexagonal chart
now say so.

### New

- **The scanner and camera window asks what the profile is for.** Three
  choices: an everyday scanner or camera profile, a profile so the scanner can
  stand in for a measuring instrument, and a printer profile measured with that
  scanner. Picking one sets the profile type, the quality and the white point
  handling to suit it, so the settings that decide whether the profile is any
  good are not something to remember. Nothing is locked. Change a setting
  afterwards and the window says which one differs rather than changing it back.
- **Those three settings are also chosen from the size of your target.** Under
  100 patches ChromIQ starts from Shaper + matrix at Medium quality with "Map
  chart white to white"; at 100 and above from the XYZ table at High with "Scale
  white to a perfect white surface". Settings you have saved yourself are never
  moved, and the window tells you when it is leaving them alone.

### Changed

- **The white point options say which profile types they suit** rather than one
  being called the default, because the previous default costs real accuracy on
  the two matrix types.
- **"Restrict white, black and primaries" now shows as ticked** when the white
  point choice includes it. The flag was always being sent; the box did not say
  so. What is stored stays your own value.

### Fixed

- **The patch-set editor could not be opened on a CR30 chart.** ChromIQ asked
  printtarg to draw the preview, and printtarg has no code for the CR30, so it
  refused the chart and printed its whole usage text. ChromIQ lays CR30 charts
  out itself, and the editor now does the same instead of asking a tool that
  cannot. Charts ChromIQ laid out are drawn by ChromIQ everywhere, and the
  values that go to printtarg are checked against what printtarg actually
  accepts before it is started at all.
- **"Save As…" in the patch editor turned a ChromIQ-laid-out chart into a
  different chart.** The saved chart came back with extra fill patches, a
  different strip grid, and without the sidecar that records its layout, which
  the measuring path reads. Measured on a real 441-patch chart: it now saves
  back identical, patch for patch and strip for strip. "Apply / Save →
  Overwrite" was never affected. If you kept a chart saved this way, save it
  again from the editor to get the layout back.
- **A message window could open taller than your screen and take its buttons
  with it.** Long messages are now widened rather than stretched, anything left
  over goes behind "Show Details", and no message window can open past the edge
  of the usable screen. macOS could not rescue the old one: a window that tall
  does not fit anywhere.
- **The patch editor window itself opened 1280 by 820 whatever screen it was
  on.** On a smaller laptop that put Apply / Save… and Close under the bottom
  edge. It now opens no taller than the screen can hold.
- **When a tool refused a chart, the patch editor showed you the tool's raw
  output.** It was the only window in ChromIQ that did. It now says what
  happened in ChromIQ's own words, quotes the one line of the tool's answer that
  means something, and leaves the rest in the log.
- **"Matrix only (forced)" in the profile Algorithm list could never build a
  profile.** ArgyllCMS's colprof has no *forced* matrix setting: choosing it
  produced no profile, no message and one line in the log. The entry is gone.
  (Corrected after publication, because this note first said colprof "has no
  such setting" and that reads wider than it should. colprof does have a plain
  matrix-only algorithm and ChromIQ offered that one too; what never existed
  was the "(forced)" variant. And matrix only was not the only entry in that
  list that could not build a printer profile: see the next release.)
- **A chart whose paper size is larger than printtarg can lay out gave the same
  wall of text.** The two custom paper boxes also offered sizes up to 9999 mm,
  and printtarg stops at 4000. Both now agree with the tool.
- **The Create Chart command preview showed CR30 users a command that cannot be
  run.** ChromIQ never ran it; the line on screen simply described the wrong
  thing.
- **A hexagonal patch was reported smaller than it prints.** The layout panel
  gave the row pitch as the patch height, so an 11.3 mm hexagon was listed as
  11.3 x 9.8 when it actually stands 13.1 mm from point to point. Hexagons
  interlock, so the pitch is real and useful, but it is not the patch: the panel
  now gives the patch size, and a separate "Row pitch (mm)" line for honeycombs.
  Nothing about the charts themselves changed, only what was reported.
- **On a hexagonal chart, two layout controls did nothing and did not say so.**
  With the strips pinned, "Patches per strip" could not change the chart, and
  "Minimum patch height (% of width)" could not either: a honeycomb interlocks,
  so its height follows from its width, and the strip count already decides the
  size. Both are now locked where they cannot work, with the reason on the row's
  information button, and both stay live where they genuinely do something.
- **Three errors in the scanner window's printer-mode help.** A scanner profile
  used as a measuring instrument can be built from a chart you made in ChromIQ,
  not only from a bought target; choosing the XYZ table does not switch on Force
  Absolute Colorimetric; and the closing advice pointed at a control the
  paragraph above it recommends against.
- **A help note contradicted the help card it sits in front of**, telling users
  on the current default that their bright paper was being flattened and to lift
  a ceiling that already sits above anything physical.
- **Layout settings restored from a chart folder are now range-checked**, not
  only checked for the right names, so a hand-edited or damaged `meta.json`
  cannot pass a value the tool refuses.

## v4.1.5-beta.10

**ChromIQ's USB driver installer had never installed a driver. Not for any of
the 28 supported instruments, not on any architecture, not once, and beta 9
shipped it.**

It was found by testing the ArgyllCMS driver path against real hardware for the
first time. Three faults were stacked so that each one hid the next, and a
fourth appeared once they were gone. Beta 9's notes said the driver helper was
proven end to end on real hardware: that was true of the CR30's serial bridge,
and not of the USB half, which is what this release repairs.

This beta also carries the scanner-window and white-point work that landed after
beta 9 was tagged.

### Fixed

- **Windows: the USB driver installer never installed a driver.** Four faults,
  each hiding the next. A ghost registry entry, left by the same instrument on a
  different USB port, still had a driver recorded against it, so ChromIQ
  believed the instrument was ready and never offered to install anything. The
  installer passed `--driver WinUSB`, which is not a wdi-simple option, so
  wdi-simple printed its usage text and exited 0, and ChromIQ read that zero as
  success: it reported an installed driver every time, having installed nothing.
  No destination was given, so the driver was extracted to wherever the elevated
  process happened to start.
- **Windows: ArgyllCMS cannot use WinUSB, and ChromIQ told users to choose it in
  seven places.** An instrument bound to WinUSB is invisible to ArgyllCMS. The
  helper installs libusb-win32 now, and the Zadig instructions no longer point
  users at the one driver that cannot work. If you followed the old advice, the
  helper puts it right: rebinding was tested on an X-Rite i1Studio, from
  `** No ports found **` back to a working instrument.
- **Windows: an install that had not finished was reported as one that failed.**
  If ChromIQ stopped watching before Windows was done, it said the install had
  failed or been cancelled. Nothing had been cancelled and nothing undone, and
  the install was very likely still running. An instrument that was never tried
  is no longer reported as one that failed either.
- **Windows: a chart restored from a Mac was invisible, and a different one was
  used in its place.** macOS and Windows store accented and umlauted filenames
  differently, and NTFS keeps the two spellings apart where APFS folds them
  together.
- **Three controls in the scanner window opened past the bottom of the screen**
  on shorter displays.
- **The scanner white-point default clipped every original brighter than the
  chart's own board.** New scanner profiles start from a better default.
- **The white-point help said "1.00 makes no change".** It is the opposite.
- **Nothing in ChromIQ said that a scanner profile used as an instrument must be
  built for that purpose.** It does now.
- **The seed box read 0** while the chart on screen had been built with
  something else.
- **The consent button was English in eleven languages**, and German had been
  quietly leaking untranslated sentences.

### Changed

- **The driver install now says what it changes before you click.** Installing
  the driver also puts a certificate into two of Windows' trust stores, and it
  stays there after the driver is gone. A button opens the full notice. This
  cannot be avoided: the driver is built for your instrument at the moment it is
  installed, so it has to be signed then too, and ArgyllCMS's own installer does
  the same thing. The notice says what was measured and what was not, rather
  than implying more.
- **The bundled CMYK profile is no longer Adobe's.** ChromIQ was redistributing
  `USWebCoatedSWOP.icc`, which Adobe's licence does not permit us to
  redistribute. It is replaced by ArgyllCMS's public-domain equivalent, and
  `THIRD-PARTY-NOTICES.md` now states the terms for everything ChromIQ ships.
- **The bundled scanner targets are marked AGPLv3**, matching ArgyllCMS, whose
  patch geometry they carry. Measured per file rather than assumed. No
  recognition file changed, and ChromIQ itself remains GPLv3.

## v4.1.5-beta.9

**Windows can now get the driver its instrument needs without leaving ChromIQ,
a colorimeter stopped refusing the most saturated patches on glossy paper, and
a measurement report that failed to save no longer looks exactly like one that
worked.**

Twenty-eight changes, from three directions at once: a Windows machine that
built and hardware-tested the driver helper, a beta tester's review of beta 8,
and a bug reported on a public forum that turned out to be ours.

### New

- **Windows: one place to get an instrument driver.** For ArgyllCMS's supported
  devices and for the CR30's USB bridge. ChromIQ checks what is bound, offers
  the right package, asks for consent before anything elevated happens, and
  says what it did. Proven end to end on real hardware: from a driverless
  device to a working COM port, with the instrument identifying in 92 ms.

### Fixed

- **A CR30 refused the most saturated patches on glossy and satin paper, and
  blamed the instrument.** A guard rejected any reading with three consecutive
  bands at exactly zero, on the premise that "a real dark patch reads a few
  percent, never exactly 0.0". The instrument's firmware clamps, so real ink
  does read exactly 0.0 — and glossy paper crosses that floor where matte never
  does, which is exactly the pattern the reporter described. It refused a vivid
  mid-tone green, and it stopped the session for good: five retries, and
  resuming met the same wall, so the chart could never be finished. Reproduced
  on our own instrument afterwards — three of five ordinary chart patches
  contain exact zeros, and two more sat one band from refusal.
  **Reported by nertog, whose diagnosis was right.**
- **A measurement report that could not be saved said nothing at all**, while a
  report that saved announced itself — so the failure looked identical to
  success. It now says so, and says first that the measurement itself is safe.
- **Saved measurement reports were re-graded by whatever the thresholds say
  today.** A report is a record of a judgement made on a day; it now keeps the
  thresholds it was judged with and the verdict it was given.
- **The file dialog's back, forward and up arrows were invisible in Neutral** —
  measured at 1.03:1 against the toolbar behind them, now 14.69:1. Light and
  Dark improve as well.
- **A test worker died with no traceback and no log**, which made every gate on
  Windows unreadable. A test ended with a thread still running; Qt aborts the
  process for that, and on Windows the abort defeats the crash handler.
- **Fourteen German sentences named buttons that do not exist**, including all
  three buttons of the window that decides whether your measurement is kept.
- **Four languages could not say where a measurement was running.** Italian,
  Portuguese, Polish and Russian glued a preposition to a translated label and
  produced ungrammatical text. Each language now supplies the whole sentence.
- **The button that declines an elevated driver install said "OK".** It says
  "Not now".

### Changed

- **The six buttons under the scanner preview wrap to the width available**,
  three to a line where they fit, with Auto align beside Check alignment —
  the action and the check that judges it. Asked for by Knut.
- **The scanner's Profile type control no longer says something nothing
  measured.** Four hundred profile builds on two targets, scored only on
  patches the fit never saw, settled where each type wins: shaper+matrix below
  about a hundred patches, a lookup table above it. The help text says so, and
  points at where you can read your own patch count. The Lab table clips
  anything lighter than the chart's own white, so the XYZ one is marked as the
  recommended lookup table.

### For developers

- The register in `docs/beta8_open_items.md` now refuses duplicate item ids, a
  fix called FIXED that names a test which does not exist, and a deferred item
  with nobody's name against it.

## v4.1.5-beta.8

**Auto align worked on 8 of the 25 bundled scanner targets. It now works on all
25 — and the reason it failed was in files we ship, not in the recogniser.**

Knut reported that auto align did not work on his charts. Basti then found it
did not work on the test file ChromIQ ships with the app. Chasing that one
report opened the whole scanner path, and most of this release comes out of it:
an under-exposed scan that quietly built a bad profile and then rated it best,
a hand-held scan tilted ten degrees accepted as correctly placed, and a
diagnostic image that drew no outline, so a correct read looked wrong. Several
of these had been shipping for months.

### Fixed — the scanner path

- **Auto align could never work on a bought target.** Every bundled `.cht`
  carried an absolute edge length in a column that ArgyllCMS reads as *strength
  relative to the strongest feature*, where the strongest must be 1.0 — 385.125
  in one file, 3600.0 in another. `scanin` scored every candidate rotation as
  `nan` and refused the match before looking at the picture. Normalised in
  place; the geometry Knut supplied is untouched. **8 of 25 targets aligned
  before, 25 of 25 now.**
- **An under-exposed scan built a profile with no warning, and the app rated it
  best.** The scan is now judged before it is trusted, and a scan too dark to
  profile from says so instead of producing a plausible, wrong profile.
- **A ten-degree hand-held tilt was accepted as a correct placement.** Keystone
  is now measured against a limit rather than assumed away: 328 correct
  placements separate cleanly from 106 wrong ones.
- **Auto align found the right answer and threw it away.** An accepted result
  was extrapolated to the fiducials a second time, moving it back off the
  patches.
- **Auto align and "Fit to the patches" are one button.** Measured over 290
  cells: neither was a subset of the other — 139 cases only the search
  recovered, 30 only the reshaping did, and "Fit" applied a placement that was
  still wrong in 41 of the 118 cases it acted on. Auto align now searches,
  reshapes, and only then submits the result to both picture checks and the
  reference agreement. **68 % → 84 % of placements land on the patches, and
  nothing wrong is applied.**
- **The alignment diagnostic drew no outline**, so a correct read looked
  misaligned; zooming it interpolated away the very edges being judged; and a
  refusal could not be diagnosed from the log. All three now say what happened.
- **A scan that is not the target you chose, an unreadable reference, and a
  scanin diagnostic image loaded as a scan** each said nothing, or blamed the
  wrong thing. Each now names what it found.
- **The profile self-check had no floor and no NaN guard.**

### Fixed — elsewhere

- **A project whose name ends in an underscore and digits silently lost its
  exports.**
- **The ICC filename and the description embedded inside it disagreed** when no
  description was given.
- **"Build anyway" was drawn as "uild anywa"** — three windows built their own
  buttons and never called the helper that has fitted them since #130.
- **Four instruction labels were painted in the one colour that cannot carry a
  word**: 1.25:1 in Light, 1.02:1 in Dark, against the 4.5:1 that AA asks for.
  Now 13.6:1, 5.1:1 and 12.1:1.
- **A self-capturing lambda on the pop-out window's `finished` signal** — the
  same shape that crashed the app through the scroll-bar fade and is now
  guarded there. Replaced with a bound method.

### Changed

- **Every warning, information and question sign in the app is ChromIQ's own.**
  The platform's signs were still showing in 70 places across 13 files. All
  three signs are drawn for Light, Dark and Neutral, and Neutral stays hueless.
- **Explanation has left the Create Chart sections for the ⓘ it belongs to.**
  Four blocks of standing text that sat inside sections now ride on the
  information icon of the control they describe, with the first line also in the
  hover tooltip so an icon carrying something says so without being clicked.
  **246 px of vertical space returned in English, 262 in German**, and the panel
  did not get wider in any of the thirteen languages.
- **The six buttons under the scanner preview read in three rows instead of
  four**, grouped by what each one acts on. The preview itself now takes the
  space the window gives it — it was pinned to its 460 px minimum however large
  the window grew, handing the rest to an empty spacer.

### For developers

- **The 34-check scanner-window sweep lives in the repository**, runs as
  `./run-sweep.sh`, and drives the real window end to end rather than a harness.
- **`docs/beta8_open_items.md` is a register the test suite enforces.** A fix
  called FIXED must name a test that exists; a deferred item must name who
  decided it and why; and the release gate refuses to go green while anything
  marked as blocking release is still open.

## v4.1.5-beta.7

**A third appearance called Neutral, a project with an umlaut that survives the
trip to Windows, and a long night of adversarial testing that found faults
which had been shipping for months.**

Two full review rounds and more than twenty attacking passes went at this
build, each one going at the round before it. Several of the worst things below
were introduced during that work and caught within the hour; they are listed
anyway, because a fault you never saw is still a fault that existed.

### New

- **Neutral, a third appearance.** A designed greyscale scheme, not Light with
  the colour turned down: one accent value, five-cell rules where the tab hues
  used to be, and every icon redrawn to read without colour. Choose it in
  Preferences beside Light and Dark. Light and Dark are byte-identical to
  beta 6 - checked view by view, not window by window.
- **Read single patches works with a CR30**, over USB and over Bluetooth,
  through ChromIQ's own driver. ArgyllCMS has never supported that instrument
  and no fork of it was needed. Pick your instrument in the window, or leave it
  on Detect automatically. Your ColorMunki and every other ArgyllCMS instrument
  behave exactly as before.
- **The scanner and camera profiling window is two panels.** The preview and
  its controls moved to the right, so the twelve wheel-turns of scrolling it
  used to take to reach the last control are now none. It fits a 1280 screen in
  all twelve languages.
- **Auto align, in the scanner and camera window.** Press it and ChromIQ tries
  to place the grid on the chart's patches for you, turning it the right way up
  if the scan was made sideways. It is an addition, not a replacement: nothing
  runs until you press it, one press puts your corners back exactly, and when
  it is not confident it says so and moves nothing rather than guessing. On
  scans it placed the grid correctly in 21 of 29 deliberately awkward cases and
  refused the other 8 out loud. On photographs it is much weaker: it refused
  most of them, and dragging the corners roughly around the chart first is what
  makes it work on a cluttered desk.
- **A profile keeps its accented name.** A profile called Müller-Prüfdruck used
  to arrive as M?ller-Pr?fdruck in Windows' colour management, because the ICC
  field ArgyllCMS fills cannot hold an accent. ChromIQ now writes the name into
  the field that can, and ChromIQ's own Profile Info window reads it back.

### Changed

- **An unmeasured calibration chart is treated as an experiment.** Replace one
  and it is not kept, the way a profile run's chart is not kept. A calibration
  that *has* been measured is always archived to the project's "cal/old"
  folder, and the window now says which of the two is about to happen. Before
  this, the window promised to keep a chart and then deleted five files.
- **The scanner window checks that what it read is the chart you meant.** It
  compares the reference against the chart, the read against the reference, and
  looks for clipping, before it builds anything.
- **Return no longer presses the button that discards a chart.**

### Fixed

- **Windows: a project name that was accepted and then could not be written.**
  Names of about 111 to 120 characters passed the name box and then failed when
  ChromIQ wrote the chart, because Windows limits the whole path rather than
  each folder name. The limit is now worked out from the longest file ChromIQ
  actually creates, and a project you already have opens whatever it is called.
- **Windows: the scanner and camera window would not fit a 1080p laptop.** Its
  smallest height was taller than the screen leaves once the taskbar and title
  bar are taken off, in every language.
- **Two projects whose names differ only in capitals no longer overwrite each
  other's chart.** ChromIQ kept the name you typed while the folder kept its
  own, so one run could hold two charts, each invisible to the other.
- **A measurement is no longer lost when you quit.** Closing ChromIQ during a
  measurement killed the reader, and the reader only writes its file on a clean
  exit, so the reading was gone with no warning. Quitting now asks, the way
  every other way out of a session already did.
- **"Save and stop" saves.** It was sending the reader a key it rejects, so the
  session never ended and nothing was written. "Keep measuring" now keeps
  measuring instead of stranding the session.
- **A single corrupt byte in a measurement no longer destroys it.** One zeroed
  byte in a `.ti3` made ChromIQ read the whole file as a different encoding and
  replace it with nonsense.
- **A project with an umlaut can be opened after a trip through a backup
  drive.** Older Mac disks store accented names differently, and ChromIQ found
  none of the project's files afterwards while telling you the chart was
  missing.
- **A bracket in a project's folder name no longer hides its chart**, and an
  asterisk no longer lets one project claim another's files.
- **A print that never happened is no longer recorded as one.** A sleeping
  printer or a cancelled dialog left a record saying the sheet had been printed
  through the profile, which then silently changed the yardstick every dE in
  the report was measured against.
- **Importing a measurement into a new project asks for the name once.** It
  used to ask twice, throw the first answer away, and leave ChromIQ saying you
  had no project open.
- **The app no longer crashes when a tool window is opened** after a spot read
  ends badly. A scroll bar was also crashing the app outright in some windows.
- **Everything ChromIQ writes now names its encoding**, so a file written on
  Windows and read on a Mac, or the reverse, arrives as what was written.
  This is GitHub issue #178.

### Known issues

- **Auto align has not been tried on a real printed chart.** Every scan it was
  measured against was generated. It is also untested on hexagonal charts, and
  it refuses small targets such as the QPcard, where it cannot reach the
  confidence it requires before moving anything.
- **Windows has now been tried, once, and the test suite could not finish
  there.** The app itself started and worked, in German at 200 % scaling, as a
  source checkout and as a packaged build. The suite hit a crash while drawing
  a checkbox and the run then hung; the hang is fixed and the drawing was
  rewritten, but nobody has yet seen a completed Windows run. Linux is
  untried.
 The encoding
  work above is the fix for a Windows-only fault, and it was written and tested
  on a Mac. If you have a Windows machine, that is the single most useful thing
  you can test.
- **The scanner window's "Correct perspective" tick has no effect** on a normal
  read. Found while testing something else, left alone rather than changed
  under a release.
- Generating a new chart over a run that holds a chart and no measurement still
  replaces it without asking. Unchanged from beta 6, and deliberately deferred.
- In Neutral, a suspect patch is still marked in red. The colour is the
  information there, so it was left rather than flattened.
- Nine controls in the Check and Refine gamut panel cannot be reached at the
  smallest window size. Present in beta 6 as well.

## v4.1.5-beta.6

**Check & Refine now asks where a measurement should go instead of deciding for
you, and four ways to lose a measurement are gone.**

Three rounds of adversarial testing went at this build, each one attacking the
round before it. Most of what follows was found that way, and several of the
faults had shipped for months without anyone meeting them.

### New

- **Check & Refine is a proper import door.** Browse for a `.ti3` that is not
  in one of your projects and ChromIQ asks where it belongs, in the same window
  Build Profile uses, in Check & Refine's own colour. It used to create a
  project without asking.
- **"Just check it where it is."** A third answer, for a measurement you want
  to look at without filing anything: nothing is copied, no project is made,
  and the report is written next to the file itself. The window says plainly
  what that costs you: no run, and nothing to look it up in later.
- **The ColorMunki's dial is drawn.** Both calibration windows now show the
  wheel turned to the mark that window is asking for: the white bar at half
  past four on the gear when it wants calibrating, at six o'clock on the target
  mark when it wants measuring. Every other instrument's windows are unchanged.

### Fixed

- **Declining to teach a CR30 its tile no longer closes ChromIQ.** Pressing
  "Not now", which that window invites you to do, ended the app mid
  measurement and took the readings taken so far with it.
- **The optional calibration window no longer closes ChromIQ either**, and its
  "Skip this step" button now does something. Both faults only appear with an
  instrument that offers optional calibration.
- **Importing a measurement can no longer end the app.** Four separate causes:
  a folder ChromIQ cannot write to, a disk that is full, a drive or share that
  has gone away, and a project whose own `project.json` has been damaged. Each
  now says what went wrong and leaves everything as it was.
- **A measurement can no longer be filed into the wrong project.** Picking a
  folder whose name contains something like a space (a Finder duplicate, an
  unzipped hand-off, a Dropbox conflicted copy) used to make an empty project
  of a slightly different name and then complain that it had no chart in it. A
  project that lives behind a symlink, on an external drive or a NAS, could
  take the measurement into whatever project happened to be open instead.
- **"Nothing has been copied" is true again.** Checking a file where it lies
  used to be followed immediately by a window offering to copy it in, and one
  click made a whole project.
- **Cancel means nothing happens.** Answering Cancel to "Where should this
  measurement go?" used to be met by a second, unrelated question about copying
  chart files.
- **A run with no settings of its own opens on your saved defaults.**
  Selecting a run made before 4.1.5, or a run that was created without a
  chart, used to leave the previous run's instrument, paper, layout mode,
  indicator checkboxes, stamp option, Guided settings and gamut options on
  screen, and then store them as that run's own. Choosing "New run" in the run
  bar is unchanged: it still starts from the run you were on, so a new run is
  "like the last one, with one change".
- **Row numbers fit the row they name.** On a tall chart the automatic size was
  taken from the patch width, so the numbers printed over each other into an
  unreadable ladder; they are now capped at the height of a row. They also stay
  inside the "Text distance to edge" limit instead of walking to the paper's
  edge on charts with more than ninety-nine rows.
- **Guided's patch estimate matches the chart it builds.** It promised 368
  patches on a CR30 A4 sheet that holds 345.
- A refused import no longer leaves a run on disk, moves you to a different
  run, or leaves the target bar naming a run that does not exist.
- A new user with no projects yet can now reach "Just check it where it is".
  The window it lives on refused to appear when there was nothing to list.

## v4.1.5-beta.5

**Row numbers can now be printed on any chart, and a preset stops naming your
project after itself.**

Two reports from Knut.

### New

- **"Show row numbers".** ChromIQ has always printed a number beside each row
  of patches on a SpectroScan and a CR30 chart, which — together with the
  letters along the top — lets you find one patch among several hundred the way
  you find a square on a map: strip A, row 12. It was never offered anywhere
  else. There is now a checkbox for it in the layout panel, next to "Show strip
  indicators", for every instrument.
- Every chart you have already made looks exactly as it did. The setting starts
  out as "whatever this instrument normally does", so nothing changes until you
  tick or clear the box yourself. Your choice is then saved with your presets
  and with the chart.
- Switching it on reserves 7.5 mm down the left edge, so there may be room for
  slightly fewer or slightly smaller patches. The estimated patch count takes
  that into account, and so does the chart ChromIQ actually builds.
- Where the clip border would be printed over the numbers, the layout inspector
  says so and offers the two ways round it.

### Changed

- **A preset no longer names your project after itself.** Loading a built-in
  preset with the name box empty used to name the project after the preset, so
  a folder, the name printed on the chart and the finished ICC profile could
  all end up called something like "i1Pro-A4-162p-1page-Portrait-w7.5mm".
  ChromIQ now asks you for a name.
- **The window that asks now takes the answer.** It has a name box, a Continue
  button, and a ⓘ that explains what makes a good name and where that name will
  show up later. Type it and the chart you asked for is built — no going back to
  a field elsewhere and picking the preset a second time.

### Fixed

- Choosing a SpectroScan or a CR30 could silently switch off the row numbers
  those two instruments have always printed.
- A preset chosen while a project was already open could rename that project
  after the preset.
- The name is now settled before ChromIQ checks whether it already belongs to a
  project, so an existing project is never quietly replaced.
- A name too long for the filesystem is refused with an explanation, instead of
  failing halfway through and leaving a half-made project behind.
- The live chart preview no longer opens a window while you drag a slider.

### Known issues

- In "Prioritise chart area", the row numbers still cost 7.5 mm of paper that
  is then left empty at the right-hand edge. This affects SpectroScan and CR30
  charts as well, and predates this release; it is being tracked separately.

## v4.1.5-beta.4

**Finding out why Bluetooth will not connect — and a magnet guard that was
silently switched off for some people.**

### Fixed

- **A tile learned over the USB cable did not protect you over Bluetooth.**
  ChromIQ files your instrument's white-tile value under the instrument's own
  id, and it was reading a different id on each connection — so the magnet
  guard looked under a name with nothing stored against it and stayed off.
  Nothing was ever measured wrongly because of it, but the protection was
  absent on the one connection that has no other defence.
- **A failed Bluetooth connection left nothing in the log.** Success and
  failure looked identical afterwards, which made "did it even try?" an
  unanswerable question.
- **The help-icon debug line was filling your log.** It recorded every help
  icon the app built — around three fifths of everything ChromIQ wrote — and
  pushed the entries that diagnose real faults out of the file. Removing it
  roughly triples how far back your log reaches.

### Changed

- **The Measure tab now says how it connected**, over the cable or over
  Bluetooth, in the session log. ChromIQ chooses for you, and until now it
  never said which it chose.
- **The Bluetooth report says more.** It counts devices that advertise no
  services at all — which is allowed, and means ChromIQ may never have looked
  at your instrument — and it is honest that a serial number you type may not
  match what the instrument broadcasts, so a silent result does not rule your
  instrument out.
- **The Tools menu is capped and scrolls.** It had grown past the bottom of
  smaller screens, where the last tools could not be reached.

### Known issues

- Bluetooth has still only been used successfully on macOS. If it will not
  connect for you, Tools → Instruments → CR30 Bluetooth report is what to send.

## v4.1.5-beta.3

**Aiming help for the CR30, a legend that gets out of your way, and the layout
controls where the help says they are.**

### New

**See where the instrument will sit.** A CR30 is placed on each patch by hand,
and its 33 mm body hides the patch the moment you lower it — so you cannot look
at what you are aiming at while you aim. The preview now draws that body to
scale, dashed, on the patch you are being asked for: line it up on screen, note
which neighbours it covers, and put the instrument down so those same neighbours
are evenly covered. A second, much smaller circle appears only when there is a
problem — the 4 mm measuring opening, shown when the patch is too small for it,
in which case part of every reading is the neighbouring patch. Both figures come
from the manufacturer's own specification. The option is in the Measure tab's
live-preview section and appears for the CR30 only.

**A Bluetooth report, for when the instrument will not connect.** Tools →
Instruments. It looks at what your computer's Bluetooth can see, whether
anything is offering the service a CR30 uses, and whether ChromIQ's own search
accepts it — so the three cases can be told apart instead of guessed at. It
writes a file you can send. Nothing it does can disturb your instrument: it is
never asked to measure and never asked to calibrate.

### Changed

**The legend fades out when you point at it**, so you can see the patches
underneath. It sits in the bottom paper margin, but on a chart whose patches run
to the edge it has to rest on the last row — now it simply gets out of the way.

**Patch size and Patch scale have moved into Basic**, next to "Prioritise patch
size", where the help has always said they were. They were in Expert Options,
collapsed, while the other layout method showed its settings in plain sight.

### Fixed

- **"Prioritise chart area" now honours your left margin.** A 7.5 mm band for
  the row numbers was reserved OUTSIDE it, so a 1 mm margin put the first patch
  at 8.5 mm. The row numbers now sit inside the margin, and the panel warns when
  it is too tight for them.
- **The margin readout says what it measures** — "Left (to first patch)" — and
  explains the two things that legitimately sit in that space.
- **A flagged patch keeps its whole red ring.** On a hexagonal chart the
  neighbouring patch was painted over part of it.
- **Loading a new chart no longer shows the previous chart's measurements.**
- **The legend no longer lands at the top of the sheet**, over the column
  letters, on charts whose strip geometry is not recorded.

### Known issues

- Over Bluetooth the learning step asks for TWO presses with the cap on, not
  one, and does not yet say so while it waits.
- Bluetooth has still only been used successfully on macOS. If it will not
  connect for you, the new report under Tools → Instruments is what to send.

## v4.1.5-beta.2

**The magnet guard now works on your instrument, not only on the one it was
built from — and you can take a reading with the space bar.**

A magnet at the CR30's measuring opening stops it measuring: it takes a white
calibration instead and hands back its stored white-tile value. That value looks
like a perfectly ordinary patch colour, so the only defence is recognising it.
Until now ChromIQ recognised ONE instrument's value, hard-coded — and the only
other CR30 anyone has measured reads up to 4.69 %R away, ninety-four times the
tolerance. On anyone else's device the check matched nothing and its owner had
no protection at all.

### New

**ChromIQ learns your instrument's white-tile value.** One press with the cap
on over USB — two over Bluetooth, where the instrument does not report that the
opening was covered and ChromIQ instead requires two identical readings, which
real measurements never are. Offered once after calibrating. That press is harmless to your calibration:
measured across three experiments on real hardware, a capped press does not move
the white reference. The value is filed against your instrument, so a second
CR30 never inherits the first one's — over USB by its serial, over Bluetooth by
its address, which distinguishes two devices on macOS, Windows and Linux alike.

**Space, or Enter, takes the reading** without touching the instrument. That is
not only convenience: pressing the instrument's own button moves it, by about
ten times its own measurement noise — 0.5 %R against 0.05 %R, both measured.
Keeping it still is measurably more accurate. ChromIQ offers the key once it has
learned your instrument's tile and refuses it before then, because a reading
ChromIQ asks for cannot report the magnet gate, and the learned value is what
stands in for it.

**A CR30 chart no longer defaults to printing spacers.** A spacer exists so a
strip reader can find where one patch ends as it is swiped across the row. A
CR30 is lifted onto each patch by hand and never swipes, so a spacer is ink it
cannot use — and the width it costs is patches per sheet. Guided already knew
this; Manual and From Profile Gamut now do too. It is a default, not a rule:
turn them back on and you get them.

### Fixed

- **Bluetooth: the remembered address is identified before anything is written
  to it.** `ffe0` is the generic service every hobby gadget exposes, and the
  next frames sent to whatever answers there are calibration commands.
- **The magnet window no longer prints its own explanation back at you** in
  capitals, labelled as something the instrument said. It did not say it.
- **"With a magnet at the opening the instrument does not measure at all"** was
  the opposite of the danger. It answers — with a plausible number, which is
  the whole reason the guard exists.
- **A reading refused as a repeat** said "bit-identical" and "the low bits", and
  blamed the magnet in a window whose advice was to press the button again.
- **Seven places quoted the "Refine / resume existing measurement (-r)"
  checkbox without its flag** — and Polish quoted a label that did not exist on
  any control.

### Known issues

- Over Bluetooth the instrument reports no serial, so its address is used to
  tell two units apart. If your Bluetooth pairing is reset, ChromIQ offers the
  learning step again rather than trusting a stale value.
- Over Bluetooth the learning step asks for TWO presses with the cap on, not
  one, and it does not yet say so while it waits — if it seems to hang after
  the first press, press again. Over USB one press is enough.
- The keyboard trigger is refused until your instrument's tile is learned. This
  is deliberate — see above — but it means Space does nothing on a fresh
  install until you have been through the one-off step.

## v4.1.5-beta.1

**ChromIQ can now measure a chart with a CR30.** It is the first instrument
ChromIQ drives itself rather than handing to ArgyllCMS.

The CR30 is a low-cost spectrophotometer with no ArgyllCMS support of any kind,
so everything here — finding it, identifying it, calibrating it, reading a patch
— is new. It was reverse engineered on real hardware over several weeks; the
protocol notes, the captures, and the experiments that turned out **wrong**, are
public at https://github.com/itsab1989/chromiq-cr30-research.

**Where it has actually been used:** macOS over USB and over Bluetooth, and
Windows on ARM over USB, each with a real instrument and a real chart. Bluetooth
on Windows and everything on Linux should work and have not been tried on
hardware — please tell us if you get there first.

### Before you start — Windows needs a driver

The CR30 talks through a CH340-class USB-to-serial chip, and Windows needs WCH's
driver for it. macOS needs nothing at all. On Linux the driver is part of the
kernel, so there is nothing to install, but your user needs permission to open
the serial port (on most distributions, being in the `dialout` group).

1. Download **CH341SER** from **wch-ic.com**.
2. Run the installer, then unplug and replug the instrument.
3. On **Windows on ARM** you need version **4.0.2026.02 (11 February 2026) or
   newer** — the older packages do not include ARM64 and will install without
   doing anything.

If ChromIQ says no instrument was found while the CR30 is plugged in, this is
almost certainly why: look in Device Manager for a device with a warning
triangle. The cable and the instrument are fine. We would like ChromIQ to tell
those two apart itself, and it does not yet.

> ⚠ **Do not use Preferences ▸ “Install USB Driver…” for the CR30.** That button
> installs WinUSB, which is right for the colorimeters it lists and wrong here —
> it would replace the serial driver and the instrument would stop being found.
> It does not offer the CR30; please do not point it at one by hand.

The full page is `docs/cr30_platform_support.md`.

### How measuring with a CR30 works

- **ChromIQ calibrates it for you.** A window shows both calibration steps as a
  picture, with the current one marked, so the two cannot be confused. There is
  no button to press on the instrument.
- **The dark reference is offered as a tick-box** on that same window, taken
  against open air — your CR30 has no black tile. It is off unless you ask for
  it, so it never becomes a second window on every measurement. Afterwards
  ChromIQ reads once and tells you what came back — see below for exactly what
  that does and does not prove.
- **ChromIQ cannot check a white calibration at all**, and says so rather than
  implying otherwise. The instrument reports the same value whatever is under
  the cap, so a calibration against the cap's green face looks exactly like a
  good one. Your eyes are the only check there is.
- **Read a patch by pressing the button on the instrument.** ChromIQ highlights
  the patch it is waiting for, and never highlights one it is not listening to.
- **Bluetooth needs no driver on any platform.** A phone app that is merely
  *connected* takes the button press exclusively, so close it before measuring
  or your readings will never arrive.
- **A Bluetooth calibration takes about three seconds.** ChromIQ remembers the
  address it last reached your instrument at, so it does not search for a device
  it has already met. If that address stops working — a different computer, a
  second instrument, a reset Bluetooth stack — it searches again by itself.

### The safety part, which matters more than it sounds

**A magnet at the measuring opening does not measure — it recalibrates.** The
instrument takes a white calibration from whatever it is resting on and returns
a stored constant, and nothing in the reply says so. A laptop lid, a fridge
door, a magnetic desk mat or the instrument's own cap will do it, straight
through a sheet of paper.

ChromIQ detects this, **refuses the reading**, stops the measurement, and offers
to retake the white calibration on the spot. Everything measured before that
moment is safe and already saved. It cannot be prevented — the only signal
arrives inside the reading it has already spoiled — but it is never accepted in
silence.

Over USB this is caught on every unit. Over Bluetooth there is no equivalent
signal, so on a CR30 other than the one this was developed on the first such
reading may not be caught. Use USB if you have the cable.

### Fixed

These affected 4.1.4 and are not about the CR30.

- **On Windows, every measurement lost its own bookkeeping.** ChromIQ's
  measuring engine reports what it is doing as it goes, and a Windows chart path
  like `C:\Users\…` was written into that channel without escaping — so the
  message carrying the strip map and the patch count was thrown away silently,
  on every measurement. macOS and Linux were unaffected, because their paths
  have no backslashes.
- **The Zadig driver instructions now warn CR30 owners.** Those steps say to
  find your instrument and give it the WinUSB driver, which is right for every
  colorimeter ChromIQ lists and wrong for a CR30 — it is reached through a COM
  port, and WinUSB would remove it. ChromIQ also now refuses outright to install
  WinUSB on a USB-serial instrument, whatever asks it to.
- **The driver window counts properly**: “device(s)” and “colorimeter(s)” are
  gone.

### Found by testing it on the bench, not by reading the code

- **The check after a black calibration cannot tell you the reference was taken
  against the right thing**, and no longer implies it can. A dark calibration
  *defines* what zero means, so whatever the instrument was pointed at becomes
  the new zero and reads as nothing a moment later — calibrated deliberately
  against white paper on a real CR30, it read back 0.004 %. What it still gives
  you is the number itself, recorded where you and we can both see it. Getting
  that step right is your eyes, not ours, and both windows now say so.
- **Every calibration message used to be erased.** ChromIQ cleared the
  measurement log after the calibration had already written to it, so the
  read-back result, the note that a white calibration cannot be verified, and
  the note about skipping the dark step were all wiped a moment after they
  appeared. Nobody had ever read any of them. The reading now also goes to the
  log file, so it survives in a problem report.
- **A dark reference that does not look dark now stops and asks**, instead of
  mentioning it in a log panel you may have collapsed. It offers to take the
  calibration again on the spot.
- **When the instrument goes away mid-session, ChromIQ says so in plain
  words** — it used to pass on the Bluetooth library's own sentence, "Service
  Discovery has not been performed yet" — and it no longer tells you the
  measurement can go ahead over a connection that is gone.

### Known limits

- The measurement preview's legend can cover the last row of patches when the
  page margin is small.
- Help cards still print with US Letter measurements on Letter paper.
- On Windows, “no instrument found” is also what you see when the driver is
  missing. The two should be told apart and are not yet.

## v4.1.4

Every "Save as…" dialog in 4.1.3 was broken. One line was at fault, nothing had
ever tested it, and it took a bug report about a help card to find it. Looking
for its neighbours turned up more: typing `0.7` into a number field gave you
`7.0`, a chart build you interrupted destroyed the chart it was replacing, and
deleting a project could destroy half of it and then tell you nothing had
happened.

### Fixed

- **Every “Save as…” dialog works again.** The help card's PDF, the profile
  report, the measurement report, the spot readings, the clip template, the
  layout-preset export, the soft-proof image, the patch colours, the i1Profiler
  export — twelve in all. The shared save dialog overwrote its own *parent
  window* argument with a folder path, so it raised an error before it could
  open, for every caller that suggests a file name. Reported against Help ▸
  SAVE AS PDF…, where it showed as “Something went wrong while writing the PDF”.
- **Typing `0.7` no longer gives you `7.0`.** On any computer set to a language
  that writes decimals with a comma — German, French, Spanish, most of Europe —
  every number field rejected the `.` you typed, closed up the digits, and left
  a number ten times too big, in range, with nothing on screen disagreeing with
  it. All fourteen fields. The one that costs the most is the patch-consistency
  tolerance under Measure: ChromIQ really sent `chartread -T7.00` instead of
  `-T0.70`, which tells the instrument to accept a strip ten times further out
  of agreement than you asked for — a measurement that looks fine and is not.
  Both `.` and `,` are now read as the decimal point, whichever your computer
  uses.
- **A chart build you stop, or that fails, no longer destroys the chart it was
  replacing.** The old chart is set aside before the build starts and put back
  on any ending that does not produce a new one — including closing ChromIQ
  while it runs. This matters most in the window the app itself tells you to
  spend waiting: between printing a chart and measuring it. Losing the chart's
  `.ti2` there makes the sheets on your desk unreadable, and because the layout
  seed lives only in that file, building again from the same settings produces
  a different chart that no longer matches them.
- **There is a Stop button on Create Chart.** Until now the only way out of a
  build was to quit ChromIQ, which was exactly what destroyed the chart.
- **Cancelling a name prompt no longer closes ChromIQ.** Loading a patch set
  with no project open, or copying in a profile that lives outside your working
  folder, asks you to name the project — and pressing Cancel there shut the app
  down instead of simply stopping. It has done that in every version since
  4.0.0.
- **A help card PDF that cannot be written no longer reports success.** ChromIQ
  asked the PDF tool whether it had complained; the tool does not complain, it
  simply paints nothing. The file itself is checked now, and an empty one is
  removed rather than left behind under the name you chose.
- **Typing the project name is no longer sluggish.** One keystroke in the
  Create Chart name field recomputed the whole page layout — a column-fit search
  measuring all 26 capital letters, over 51,000 text measurements per key
  pressed, to answer a question whose answer never changes. Measured at 82 ms a
  keystroke; now about 4 ms. The same saving applies to every layout estimate
  and to building a chart.

### New

- **ChromIQ tells you when a project of that name already exists.** Type a name
  you have used before and a line appears under the box; build, and a window
  names the folder, lists what each of its runs holds, and lets you choose:
  carry on in a run you pick (a new one by default, which costs nothing),
  replace the project after a second confirmation, use a different name, or
  stop. Before this, ChromIQ opened that project in silence and built into it.
- **You choose which run to continue in**, in that same window, instead of the
  project's own last run being taken for you.
- **Backing out of a built-in preset now really changes nothing.** Pick one from
  the ★ list, read the window, press Cancel, and ChromIQ used to leave you in
  Manual with the preset's whole layout in the panel — and quietly kept four of
  its choices as your app-wide settings, including whether the ChromIQ layout
  engine is on and how the ruler marks are drawn. Everything goes back now: the
  mode, every setting on the page, the layout, the name field, any section you
  had opened, and the preset list itself, which returns to the preset you
  actually had and can be used to choose that one again. Triple Density in
  particular used to come back ticked but dead: the layout it hides was gone, so
  unticking it afterwards changed nothing.

### Fixed — your work is safer than it was

- **Deleting moves things to your Trash** — the Recycle Bin on Windows, the
  Wastebasket on Linux — so you can bring them back until you empty it. It used
  to remove files one by one and stop at the first it could not: one read-only
  sub-folder was enough to destroy ten files of twenty-nine, `project.json`
  among them, so ChromIQ could no longer open what was left — while the window
  said “Nothing was changed.” A move to the Trash cannot half-happen, and when
  there is nowhere to put the files nothing is touched at all.
- **The Delete window stops claiming nothing will be lost when something will.**
  Re-making a chart on a measured run archives the measurement and the profile
  into the run's “old” folder, on purpose, because they cannot be recreated.
  Delete only looked at the live files, so such a run reported itself as never
  measured — and the window said so while deleting two archived measurements, a
  profile and both averaging readings. It now counts what is in “old”, names the
  dates, and mentions the copy of the chart your measurement was taken with.

- **The individual readings of an averaged measurement are no longer deleted.**
  Re-generating a chart archived the measurement and the profile and then
  removed `reads/read1.ti3`, `read2.ti3`… — instrument readings taken by hand,
  which nothing can bring back. They are archived with everything else now.
- **Projects in a sub-folder of your ChromIQ folder are proper projects.**
  Renaming one used to fail and leave an empty project at the new name while
  abandoning the real one; the “this profile has already been built” guard could
  not see its profile; and “Delete the whole project” refused and said nothing.
- **Replacing a project is all or nothing.** It could fail half way and leave
  the folder neither the old project nor a new one, while reporting that nothing
  had changed. Everything is put back now, and a failure is a window rather than
  a line in the log.
- **A project folder with an unreadable or hand-edited `project.json` can no
  longer crash Generate Chart**, or steer ChromIQ outside the project folder.
- **The clip-template export lists your files again.** The dialog was handed a
  label where it expected a file filter, so it filtered on the words in it.
- **Your log is readable.** Nine minutes of use produced 2,315 lines, of which
  1,813 were the image library talking to itself and 101 were ChromIQ. The noisy
  libraries are quiet now, so a real fault is not pushed out of a rotated log by
  chatter — and ChromIQ says plainly whether it opened an existing project or
  created a new one.

### Also

- The website's Create Chart, Measure and scanner sections were rewritten, and
  two sections added: keeping a profile honest over months, and where your work
  lives.

## v4.1.3

ChromIQ now speaks thirteen languages properly, not just completely — every
catalogue was read end to end and the words on one screen were made to agree.
Thirty-eight new i1Pro charts, printable help cards, and a long list of things
that quietly did the wrong thing.

### New

- **Thirty-eight new i1Pro charts.** Nineteen with 7.5 mm patches in A4, US
  Letter and A3, and nineteen with 8 mm patches, from 156 up to 4,212 patches.
- **Help cards can be printed.** A Print… button on any open card, laid out for
  the paper rather than the screen, with the ChromIQ wordmark and the spectrum
  band on every page.
- **Three more help cards** — one each for the tools that had none: designing a
  patch set, reading single patches, and the patch cube.
- **A Close Project button**, third along the top left, beside Open Chart File.
- **Keyboard shortcuts appear in tooltips**, spelled the way your own keyboard
  spells them — ⌘1 on a Mac, Ctrl+1 everywhere else.

### Changed

- **All thirteen languages were swept for consistency, one at a time.** The same
  control was often named several different ways in one language — and the
  second name usually already meant something else. Italian used one word for
  both *chart* and *paper*, so the scanner help said "clean the glass and the
  paper" when it meant the chart. Polish used its word for *tab* to mean
  *chart*. Portuguese used one word for *gamut*, *gamma* and *range*. Russian,
  Norwegian and Chinese each carried five names for one thing. Around 2,900
  entries were corrected.
- **French now addresses you informally**, matching German, Dutch, Italian and
  Spanish — it had been split down the middle, saying "vous" in a help text and
  "tu" in the tooltip beside it. **Portuguese is consistently European
  Portuguese**, including the update notice everybody sees.
- **Preferences opens in about 0.7 seconds instead of 2.3.**
- **The Red River presets are Knut's own again**, and the i1Pro preset list is
  ordered by paper, then patch count, then page number.

### Fixed

- **A project name containing a dot split its files in half**, and the project
  could not be measured. 120 of the 130 built-in presets suggest such a name.
  Projects already broken this way are repaired when you open them, and nothing
  is deleted — the old files are kept.
- **Guided mode used ArgyllCMS printtarg instead of ChromIQ's own layout
  engine** whenever "Print info in left clip area" was ticked — a setting
  written only by the Manual tab, which Guided has no control for. So a box
  ticked in one tab changed what another tab produced, invisibly, while the
  screen still said "ChromIQ layout engine".
- **Your chart was re-drawn and overwritten when you had not asked for it.**
  With auto-update preview on, changing module, picking a different run, loading
  a preset, pressing Reset or opening a chart file each silently re-laid out the
  chart and rewrote it to disk.
- **The Create Chart ▸ Manual panel was cut off on the right in nine of the
  thirteen languages** — controls under the scrollbar, the ⓘ buttons sliced in
  half. Several controls had been sized against the English word they show, so
  German's "automatisch" arrived as "natisch".
- **The margin check no longer accuses a chart of breaking its own margins.** 45
  of the built-in charts are drawn at 200 dpi and land exactly on their declared
  margin, but were reported inside it because a chart's edges can only fall on
  whole pixels.
- **Duplicating a run dropped 17 of the 27 things it records**, including every
  Create Chart setting.
- **ChromIQ could create a project you never asked for** — three separate ways,
  including simply opening the Tools menu.
- **Closing a window could crash ChromIQ.**
- **A wrong ArgyllCMS path could lock you out of the app.**
- **Help text named buttons that do not exist** — twenty of them, including a
  tick box removed in 2025 and advice the app itself warns against. Corrected in
  English and in every language.
- **Printed help cards came out at a third of their size on macOS**, lost whole
  pages of text silently, and printed sheets with nothing on them.
- **ChromIQ left large temporary files behind** after soft-proofing.
- **Print Chart's settings were lost when you closed the project**, and settings
  could follow you from one run into another.

### Known issues

- A chart built in Guided and then continued in Manual is judged against layout
  defaults rather than your instrument's minimums, so it can show a green
  "Margins: OK" on a sheet the instrument cannot read. Judge margins from the
  Guided panel. See issue #171.

## v4.1.3-beta.21

Every language got read end to end, and the panel that had been quietly cut off
in nine of them now fits.

### Fixed

- **The Create Chart ▸ Manual panel was cut off on the right in nine of the
  thirteen languages.** Controls ran under the scrollbar, the ⓘ buttons down the
  right edge were sliced in half, and the panel could be swiped sideways. The
  worst was the row of preset buttons — in German, "Auf Vorgabe zurücksetzen /
  Vorgabe aktualisieren / Vorgaben bearbeiten" needed 60 px more than the panel
  has, Swedish 155 px more. Those buttons now wrap onto a second line instead of
  pushing everything sideways, so all three labels are readable in full.
  English is unchanged.
- **Several controls were sized against the English word they show.** The
  patch-size boxes reserved room for "auto" and cut German's "automatisch" to
  "natisch"; the "Stamp settings used on the chart" tick box lost its last
  letters behind its ⓘ; three tick boxes in the margin panel and a Portuguese
  label ("mático") were clipped the same way. Each now measures the word it
  actually shows.
- **The Measure tab scrolled sideways in Spanish, Portuguese and French** — a
  dropdown pinned to an English width.

### Changed

- **All thirteen languages were swept for consistency, one at a time.** The
  same control was often named several different ways in one language — and
  sometimes the second name already meant something else. Italian used one word
  for both *chart* and *paper*, so the scanner help said "clean the glass and
  the paper" when it meant the chart. Polish used its word for *tab* to mean
  *chart*, colliding with itself in a single sentence. Portuguese used one word
  for *gamut*, *gamma* and *range*. Russian, Norwegian and Chinese each had
  five names for one thing. Around 2,900 entries were corrected in total.
- **French now addresses you informally**, matching German, Dutch, Italian,
  Spanish and the others — it had been split down the middle, saying "vous" in
  a help text and "tu" in the tooltip beside it.
- **Portuguese is consistently European Portuguese**, including the update
  notice everybody sees.
- **Help text no longer names buttons that do not exist.** Twenty English
  strings pointed at controls that had been renamed or removed — one described
  a tick box deleted in 2025, and another gave advice the app itself warns
  against. All corrected, in every language.

## v4.1.3-beta.20

Changing tab, picking a run or loading a preset re-drew your chart and wrote it
to disk. And the help cards named eleven buttons that do not exist.

### Fixed

- **Your chart was re-drawn and overwritten when you had not asked for it.**
  With "Auto-update preview" on, generating a chart in Guided and then clicking
  MANUAL replaced the sheet you had just made — 450 ms after the click, with
  nothing touched. It happened again when you merely selected a different run in
  the run bar, when you loaded one of your own presets, when you pressed Manual's
  "Reset", and when you opened a chart file with Open Chart File (.ti2). Filling
  the layout boxes on your behalf looked exactly like you turning a knob, so the
  live preview believed the layout had changed. It now settles at the end of each
  of those operations; a change **you** make still refreshes the preview at once.
- **Eleven help-card steps named buttons that do not exist.** Six described a
  "Disable bidirectional reading" tickbox that was removed from ChromIQ in 2025 —
  the real control is the Measure tab's "Strip recognition" row with its "Auto"
  box. Seven said "Analyse" where the button reads "Analyse Profile Quality", two
  said "Load .ti3" where there is an icon and a folder button, and others named
  "Use as Pre-conditioning Profile", "Read again & average" and "Empty the run".
  All corrected in English and in all twelve languages.
- **A help card advised something the app itself warns against.** The new
  strip-recognition text told you to switch off "Auto" and force bidirectional
  reading if you scan in one continuous motion. On a fixed-order chart that can
  latch onto the wrong strip and quietly build a profile with colour casts —
  which is why ChromIQ shows a warning when you do it. The cards now say to leave
  "Auto" ticked and let ChromIQ choose.
- **A help card said "Auto" picks the strip-recognition mode from your chart
  and your instrument.** It reads the instrument alone — so on an i1Pro with a
  fixed-order chart it chooses bidirectional reading, which is the case ChromIQ
  separately warns you about. The card now says what Auto really does.
- **The margin warning named the wrong minimum in every language but English.**
  When a margin came out short, the panel had to say whether it missed your
  instrument's minimum or the one the chart itself was laid out to. It decided
  by inspecting a translated sentence, so outside English it always said
  "instrument" — quoting a figure no instrument setting carries.
- **"Check && Refine" appeared with two ampersands** in three help texts.
- **A US Letter help card printed a sheet with nothing on it** — the
  "Your first profile" card, after its text grew.

### Changed

- **The margin check no longer tightens itself on a coarse chart.** beta.19
  capped the allowance at one pixel of 200 dpi; that made correct charts accuse
  themselves. A factory preset changed only from 200 to 180 dpi reported "Top
  margin 33.9 mm is below the 34 mm minimum" against a layout that sits exactly
  on its box. A chart cannot be measured more finely than the pixels it is drawn
  on.
- **The "room left on the last page" hint no longer contradicts itself.** On a
  Guided chart it read "space for about 22 more patches on it (the page holds
  about 0 in total)". Both numbers came from re-deriving a page the recipe cannot
  describe, so the hint is now left out for those charts rather than guessed at.

### Under the hood

- One design specification, `per_target_settings.md` §7 B, prescribed a guard
  that cannot work — the handler it governs fills the panel twice and the second
  fill runs after the guard is down. Rewritten to describe the shape that holds,
  marked as awaiting confirmation.
- Three tests that could not fail were removed or repointed: a function nothing
  called, and the run-switch test the specification says nothing ships without,
  which had been passing against a stand-in class with no timer.

## v4.1.3-beta.19

Guided mode has been quietly using the wrong layout engine since June, and the
twelve translation catalogues are complete.

### Fixed

- **Guided mode used ArgyllCMS printtarg instead of ChromIQ's own layout
  engine** whenever "Print info in left clip area" was ticked. That setting is
  written only by the Create Chart ▸ Manual tab's "Save as defaults" button, and
  Guided has no control for it — so ticking a box in one tab permanently changed
  what another tab produced, invisibly. Meanwhile the Guided screen said
  "ChromIQ layout engine" and predicted the engine's patch count, so the number
  on screen could differ from the chart that was built. Present since
  2026-06-30, in the very change that was supposed to make Guided engine-only.
  **If you had that box ticked, your charts will now look different** — see
  below.
- **The chart preview told you to press a button that could not help.** A
  freshly made Guided chart showed red marker dashes captioned "Markers not on
  this sheet yet — press Generate Chart", but the marker settings live only in
  Manual, and Guided charts never carry markers — so pressing Generate Chart
  rebuilt the same sheet and the message came back. Guided now shows what the
  sheet actually carries, and never claims a change is pending.
- **The margin check no longer accuses a chart of breaking its own margins.**
  45 of the built-in charts are drawn at 200 dpi and land exactly on their
  declared margin, but were reported 0.05 mm inside it because a chart's edges
  can only fall on whole pixels. The check now allows one pixel — the smallest
  error a printer can actually make — instead of a fixed figure that happened to
  suit 300 dpi.
- **A built-in chart preset could build the wrong chart.** After choosing
  Presets ▸ Default, picking the same built-in preset again produced a chart
  with 6 strips instead of 7, no clip band, no ruler marks and none of the
  preset's margins.

### Changed

- **All twelve languages are complete** — every text ChromIQ shows is now
  translated in German, Dutch, Spanish, French, Italian, Portuguese, Swedish,
  Norwegian, Polish, Russian, Japanese and Simplified Chinese.

### If you had "Print info in left clip area" ticked

Your Guided charts were being laid out by printtarg and will now be laid out by
ChromIQ's engine. For i1Pro on A4, US Letter and Legal nothing changes — 484
patches, 22 strips, as before. A4R gains 16 patches, US Letter rotated gains 17,
and A3, 11x17 and A2 gain a whole extra strip. Every affected sheet looks
different. Nothing you have already measured is invalidated: a Guided chart
rebuilt from its own record always produced a different sheet anyway, because
printtarg charts record no layout recipe.

Gate: 7452 passed, 140 skipped, 2 xfailed.


## v4.1.3-beta.18

Fixes found by reviewing what beta.17 actually shipped, plus Knut's beta.17
notes. **Two of these were security or data faults in the repair added one
release earlier.**

### Fixed

- **The project repair could rename files outside the project.** The repair
  added in beta.17 executed its record of planned moves without checking that
  the paths stayed inside the project folder, so a project folder containing a
  crafted or merely corrupted `name-repair.json` — the kind of folder people zip
  and send each other — could rename files anywhere the recipient can write, the
  moment they opened it. The repair now refuses any entry that points outside
  the project, and says so in the log. Proven both ways: the shipped beta.17
  moves the file, this build does not, and a legitimate rename inside the
  project still runs.
- **The repair's undo record could be lost exactly when it was needed.** It was
  written by truncating the file first, so running out of disk part way through
  left an empty record *after* the renames had happened. It is now written to a
  temporary file and swapped in atomically — a move ChromIQ cannot record is a
  move it does not make.
- **One malformed entry no longer disables the repair for that project for
  ever.** A path containing a NUL byte raised an error the repair did not catch.
- **The Red River charts no longer show the “Full layout setup” label** (Knut,
  beta.17). The label means the patch-set editor has the chart's complete
  design; those six ship the page layout but not the colour-set design, so it
  overpromised. 115 of the 130 built-in charts carry it — the six Red River and
  the nine “by Pharmacist” charts do not.
- **The second patch-set warning is gone.** Ticking “Edit patch recipe (override
  preset)” already opens a window saying the loaded patches will be replaced,
  and that box is shown for a patch set you loaded yourself, not only for a
  built-in preset — so a second window at Generate time interrupted a decision
  you had already made (Knut).
- The landing page now says ChromIQ ships **130 ready-made chart presets**, and
  its embedded version metadata no longer claims 4.0.0.

### Also

- Three comments in the source described behaviour the code does not have,
  including one claiming the app tells you when it has repaired a project. It
  does not — for now that is a log line only, and the comment says so.
- An 842 KB stray backup file that a blanket `git add` had committed is removed,
  and that class of file is ignored from now on.

### Known, and deliberately not changed in this build

- A built-in ColorMunki preset warns that its own right margin is 0.055 mm below
  its declared minimum, and only when chosen through the ★ overlay. The printed
  chart is correct and the warning is accurate; the discrepancy is in the layout
  engine, not the check, so widening the check would hide it. Tracked as #167.

Gate: 7431 passed, 140 skipped, 2 xfailed.


## v4.1.3-beta.17

Knut's Red River presets, exactly as he sent them, and the repair for projects
whose files were split by the dotted-name bug.

### Fixed

- **The Red River presets are Knut's own again.** All six were replaced with the
  files he supplied, field for field: the markers-per-patch values he chose (5
  on the i1Pro charts, 7 on the ColorMunki A4 8-page, 3 on the rest), his
  ColorMunki margins, the clip band on the right with flip 180° for ColorMunki
  and on the left for i1Pro, and his 9-page ColorMunki charts in place of the
  10-page ones. The old six were removed entirely rather than edited.
  A test now reads his files from a fixture and checks every field, so a value
  cannot be changed by accident again — which is how the previous set drifted:
  a ruler-marks change wrote one markers-per-patch value across all six and
  overwrote the per-chart values he had measured.
- **“Full layout setup” is back on the preset list** — on every built-in except
  the nine “by Pharmacist” charts, which is the rule Knut asked for. It is added
  to the displayed row only, never to the preset's stored name: that name feeds
  both the suggested project-folder name and the key custom presets are matched
  against, so marking it there would have renamed 121 suggested folders and
  orphaned every custom preset already saved.

### Added

- **Projects broken by the dotted-name bug are repaired when you open them.**
  Charts built before beta.16 under a name containing a dot had their files
  written under two different names, which left the project unmeasurable.
  ChromIQ now puts those files back under one name on open, so sheets you have
  already printed stay readable and nothing has to be rebuilt or reprinted.
  It renames only files it can prove came from that bug — a truncated name, no
  file already holding the correct one, the run's own `.ti1` confirming the full
  name, and the strip file that only ChromIQ's own layout engine writes. Every
  rename is recorded in `name-repair.json` inside the project, so it can be read
  back or undone by hand, and the record is written before anything moves, so an
  interrupted repair finishes rather than restarting. Set
  `CHROMIQ_NAME_REPAIR=dry` to see what it would do without doing it, or `off`
  to switch it off entirely.
- **Preferences ▸ Chart Layout jumps to the density your layout is saved under**
  when you switch instrument, and says so underneath, instead of landing on the
  first density and showing factory defaults — which read as “my settings are
  gone” when they were one box away. The paper you are working on never moves.

Gate: 7426 passed.


## v4.1.3-beta.16

Knut's beta.15 review, plus four faults nobody reported — three of which were
losing or hiding data, and one of which has been shipping since 4.0.0.

### Fixed — data, and the ones that were never reported

- **A project name containing a dot split its files in half.** ChromIQ builds
  every file of a run from the project name, and in several places it worked
  that name out by asking Python to remove the extension — from something that
  has no extension. Python then reads “.0mm” in
  `…-Portrait-w10.0mm` as the extension and removes it, so the `.ti2`, the
  printable pages and the strip data were written under a shortened name while
  the `.ti1` kept the full one. **The project could not be measured**: chartread
  was handed a name whose `.ti2` did not exist. Duplicate Run was greyed out,
  and reopening the project showed no chart pages. **120 of ChromIQ's 130
  built-in charts suggest a name with a dot in it**, so this was the normal
  case, not an exotic one. Fixed in the chart builder, the scanner-target
  writer, the reference-file importer and the image writer — the last two of
  which also broke the scanner→profile flow outright, because ArgyllCMS's
  `scanin` builds those filenames by joining strings while ChromIQ predicted
  them by stripping extensions. There is now one rule, in `core/stem_paths.py`:
  artefact names are built by joining, never by guessing what part of a name is
  an extension.
- **Duplicating a run dropped 17 of the 27 things it records**, including all
  five settings groups and the patch-set editor's own state, which its own
  documentation says cannot be recovered from the chart file. A duplicate now
  carries everything that describes the files it copied. `per_target_settings.md`
  §6.3 had required this all along.
- **A duplicate lost the “this chart does not match this measurement” warning**
  while copying both the chart and the measurement — so it handed back a chart
  that did not describe the measurement beside it, silently.
- **The “Your duplicated run is ready” window had never once opened.** It raised
  on the way up because one placeholder in its text was never given a value.
  Present since 2026-08-01 and shipped in 4.0.0.
- After deleting a run, a duplicate's record of where it came from pointed at
  whichever run had since taken that number.

### Fixed — from Knut's beta.15 review

- **Keyboard shortcuts in tooltips now show the keys your own keyboard has.**
  ⌘ and ⇧ were written into the text on every platform; a Windows user was
  shown a key they do not have. All thirteen translations re-synced.
- **The Dictionary card sits beside the Keyboard shortcuts card again.** Adding
  three cards in beta.15 pushed it onto the row above.
- **The three cards that had no icon now have one.** They were not the wrong
  icons — nothing was drawn at all.
- **The help sentence on the profile-run bar is no longer cut in half** when it
  wraps to three lines, or laid over the buttons when it wraps below them. The
  cause was an ordering one: the bar's height was worked out before it was told
  how wide it would be, so it was always sized for the previous window width.
- **Choosing a built-in chart with no project open no longer creates a project
  you did not ask for.** The guard added in beta.15 was defeated one line
  earlier: choosing a preset fills the name box with the preset's own name, and
  the guard then read its own suggestion as the user's answer.
- **The i1Pro preset list is in order.** Its A4 block interleaved the 7.5 mm and
  8.0 mm charts; the Letter and A3 blocks already read paper → patch width →
  patch count, and A4 now matches them. No other family's order changed.

### Changed

- **Preferences opens in about 0.7 seconds instead of 2.3.** The cost was one
  preview being redrawn up to thirty times while a recipe loaded, and discarded
  twenty-nine times. It is shared with Create Chart → Manual and the layout
  editor, so every preset load anywhere in the app got the same time back.
- The clip-strip preview no longer keeps the height of whichever band you looked
  at last when it is empty.

### Note on the Red River charts

An earlier note in development claimed the ColorMunki charts printed a blank
stripe where the logo belongs, and that a flag had been changed to fix it. That
was wrong: the flag is not read for that instrument, the logo band was already
printing, and the change altered nothing. It was never released. Knut's updated
Red River presets have arrived and are not in this build — they are waiting on
two questions about his own files.


## v4.1.3-beta.15

Knut's review of beta.13, in full. Every one of the faults he reported turned
out to be larger than it looked from the outside.

### Added

- **Three new help cards**, one for each of the tools that had none: “Design a
  custom patch set for a chart”, “Spot-read the colour of a surface”, and
  “Show or compare a chart's patch set in 3D”. Each explains what every button
  in the window does, and the patch-set card answers the question Knut asked
  directly — “New patch set” replaces what is in the window, “Add” extends it.

- **Keyboard shortcuts now appear in tooltips.** Hovering a button that has a
  shortcut shows it in brackets after the name — “Open Project (⌘O)”. The five
  main buttons, one per tab, had no tooltip at all before; they now carry both
  a name and their ⌘↵ shortcut.

- **Nineteen new i1Pro charts** with 7.5 mm patches, in A4, US Letter and A3,
  from 162 to 4212 patches. Two older A4-924p charts were withdrawn.

### Fixed

- **Help cards printed blank pages.** A table row that would not fit was moved
  two pages on instead of one, leaving a whole sheet carrying nothing but the
  repeated table header. Eight such sheets across the eighteen cards. “Overview
  of Main Actions” goes from 5 sheets to 3, and the folder guide from 12 to 9.

- **The patch size shown for a chart was wrong by a fifth.** All nine of the
  “by Pharmacist” charts reported patches 20 % larger than they are — 8.99 mm
  where the true size is 7.48 — because ChromIQ read the wrong figure for the
  chart's resolution and fell back to assuming 300 dpi. The two panels beside
  the preview now agree with each other and with the printed sheet.

- **The margin guide lines sat in the wrong place on later pages.** On any
  chart with roughly more than twenty-one strips a page, the top margin was
  measured to the strip labels instead of the first row of patches — 8 mm where
  38 is right. It also raised a false warning that the top margin was below the
  instrument's minimum, and overstated the strip length by 24 mm.

- **Settings in Preferences ▸ Chart Layout vanished when you switched
  instrument.** Changing the instrument reset the density box to its first
  entry, so ChromIQ looked for settings that had never been saved under that
  combination and showed its own defaults instead. Nothing was ever lost from
  disk — cancelling and reopening brought it all back — but there was no way to
  tell that from the screen. The tab now says which you are looking at, and
  explains that it opens on the combination your current chart uses.

- **Choosing a preset with no project name created one you did not ask for.**
  It made up a folder named after the date and built the whole chart into it,
  with no message at all. ChromIQ now asks for a name. Two further routes that
  could invent a project have been closed as well — including one where merely
  asking “is anything at risk here?” created the folder.

- **File dialogs opened in your home folder.** Eight of the nine started there
  rather than in your ChromIQ folder, including “Open Chart File (.ti2)”.

- **Help text sent you to a button that had moved** — and, worse, to a button
  that still exists in that spot and does something else. Preferences was
  described as being at the top left when it is at the top right.

- **Three tooltips told Mac users to press “Ctrl”.** The chart editor's Undo and
  Redo said Ctrl+Z while the Help card, two clicks away, said ⌘Z for the same
  key. Fifteen more hard-typed shortcuts were sitting in the translations, each
  wrong in its own language's spelling.

- **Importing a set of charts could quietly change every chart in a family.**
  The check that is meant to catch a chart that does not belong compared each
  batch against its own first file, so a difference shared by the whole batch
  passed unnoticed. It now compares against the family ChromIQ ships, and
  refuses rather than folding the difference in.

- **Importing chart-layout settings could overwrite the ones you had.** The
  import accepted any JSON file and replaced real settings with defaults.

- **The Start Measurement button lost its keyboard hint.** It was the only one
  of the five main buttons that did not show its shortcut.

### Behind the scenes

- The test suite could write into your real ChromIQ preferences folder. Only
  one test reached that far and it happened to guard against it, but nothing
  enforced it; the suite now redirects the preset store to a scratch folder the
  way it already does for the demo projects.

## v4.1.3-beta.14

### Added

- **A "Close Project" button.** Third along the top left, beside "Open Chart
  File". It puts ChromIQ back to the way it looks on a fresh install, with no
  project open. Nothing is deleted and nothing on disk changes — every run,
  chart, measurement and profile stays exactly where it is, and "Open Project"
  brings it all back. Only what you have typed and not yet used is let go: the
  name in "Printer profile project name" and the run description beside it. A
  confirmation window explains all of that before anything happens, and the
  button is greyed with a reason when there is no project to close.

- **A greyed tab now tells you why.** During a measurement or a profile build
  the other tabs are locked; hovering one used to say nothing at all, which
  read as a fault rather than a lock. Each greyed tab now explains what is
  running and when it will come back — and its own explanation is put back
  afterwards, so a verification run's "not for a verification" note survives a
  measurement.

- **A keyboard shortcut for the top-left buttons.** ⌘O / Ctrl+O opens a
  project, ⇧⌘O / Ctrl+Shift+O opens a chart file. Both obey the same locks as
  the buttons themselves.

### Fixed

- **ChromIQ could create a project you never asked for — a third way.** Simply
  opening a loose chart file with nothing loaded was enough: the question "is
  this chart inside my project?" created one to compare against, leaving a
  folder named after the date beside your real work. The app then thought it
  was working in that phantom, and the next chart you built went into it.

- **Closing the Soft-proof window could stop ChromIQ noticing that anything
  had finished.** Opening Soft-proofing and closing it again quietly detached
  the part of ChromIQ that listens for a tool completing. The next measurement
  would read the whole chart and then appear to hang for ever: the tabs and the
  buttons along the top stayed greyed, because nothing was left to hear that it
  had ended. Only quitting and reopening cleared it.

- **Soft-proofing removed the picture you were looking at.** Changing the ΔE
  threshold, the rendering intent or the highlight colour started a new proof
  and deleted the previous one's files immediately — so the preview went blank
  and "Save proof" quietly did nothing while still looking available. The old
  files are now kept until the new proof is ready.

- **A patch set you loaded was not the one ChromIQ built.** After loading an
  i1Profiler patch set or a .ti1 and pressing "Generate Chart", ChromIQ could
  quietly build a completely different chart from a fresh patch calculation —
  measured, two patches in and 525 out, with no message beyond a line in the
  log. It happened for two separate reasons: in Guided mode the loaded set was
  ignored outright, and in Manual mode the act of binding the set to a run
  reset the patch-recipe settings, which ChromIQ then read as you having asked
  for a different chart. Unlocking "Edit patch recipe (override preset)" and
  changing a setting still gives you a fresh chart, as it always did.

- **Loading a second patch set discarded the first.** After loading a patch set
  and then loading another — or having a second load fail — the first one was
  deleted from disk while ChromIQ still believed it was in use. Pressing
  "Generate Chart" then silently built a completely different chart from a
  fresh patch calculation, with only a line in the log to say so.

- **A wrong ArgyllCMS path could lock you out of the app.** If a tool could not
  start at all — a mistyped path in Preferences, a moved installation — nothing
  ever reported that it had failed. The window stayed greyed as though the
  build were still going, including Preferences itself, which is the one place
  the path could have been corrected. The only way out was to quit and restart.
  ChromIQ now says which program it could not start and points at the setting
  that fixes it.

- **The "Close Project" button stayed greyed after generating a chart or
  opening a project.** It was watching the wrong thing.

- **Building a chart left the rest of the window live.** You could switch to a
  different project, open another chart, or open the Tools menu while targen
  and printtarg were still writing into the current run. A measurement and a
  profile build had always locked those buttons; a chart build now does too.

- **Print Chart's settings were lost when you closed the project.** A change to
  Rendering intent made on the Print Chart tab was not written down if you
  closed the project from that tab — the same change made on any other tab was
  kept.

- **A measurement and a profile build running together unlocked the tabs too
  early.** Whichever finished first re-enabled everything, leaving the window
  open for editing while the other was still running.

- **ChromIQ left large temporary files behind.** Soft-proofing wrote a fresh
  set of full-size TIFFs for every proof — around 60 MB — and never removed the
  previous ones, so nudging the ΔE threshold a few times could leave hundreds
  of megabytes on disk until the next reboot. The patch-set editor's "Apply"
  left a complete chart behind every time it ran. Six more places did the same
  on a smaller scale. All are now cleaned up.

- **The patch-set editor described what it does incorrectly.** Its "Overwrite"
  window said the page layout was carried across and locked. Neither was true:
  only the patch set moves, the layout comes from the Create Chart tab, and the
  page-layout panel stays editable. It also said measurements were "kept" when
  they are moved into the run's "old" folder. The window now says what actually
  happens.

- **A project deleted outside ChromIQ came back.** If "restore last session"
  was on and you had removed the folder in Finder, ChromIQ still believed the
  project was open and would recreate it.

- **A new project no longer starts with a name you did not choose.** The
  "Printer profile project name" box was pre-filled with "ChromIQ Test Chart",
  so a brand-new install showed a location line pointing into a project that
  did not exist. The box now starts empty, and pressing "Generate Chart"
  without a name asks for one instead of inventing "Printer_Paper_Type_Instr"
  plus the date.

- **Japanese and Chinese folder guides read correctly.** Lines no longer begin
  with a comma, a full stop or a dash left stranded at the margin.

## v4.1.3-beta.13

### Fixed

- **Closing a window could crash ChromIQ.** Three buttons and labels were put
  back by a timer that outlived them — the scanner window's "Saved ✓" flash for
  1.4 seconds, the Measure tab's status message for **8**. Close the window
  inside that time and the timer reached for something that no longer existed.

- **Two paths created a project you never asked for.** Opening the Tools menu
  with nothing loaded was enough to make ChromIQ name a project, and the next
  thing you did created the folder. Worse, the patch-set editor's "Save & apply"
  wrote its chart into that invented folder — leaving a folder with no project
  in it that ChromIQ could never find again — and then made a second, real
  project beside it. Applying a chart with no project open now says so and
  changes nothing.

- **The Build Profile tab stayed clickable during a measurement.** It was
  disabled when the measurement started and re-enabled three lines later by
  another part of the same code, so you could walk into a build mid-read.

## v4.1.3-beta.12

### Fixed

- **A table row no longer leaves its bottom edge on the next page.** Knut
  reported "an empty line below the header row, before next row with content
  starts" on the "Overview of Main Actions" and "Where are my files?" cards.
  The rule that keeps a row off a page break was ending the page *inside* the
  row above it — so every cell's text landed on the right page while the row's
  own padding and closing border were painted overleaf, under the repeated
  header. A straddling row is now moved whole.

  **This costs paper**, and the two cards with very tall rows pay for it:
  "Overview of Main Actions" goes from 3 pages to 5 on A4 and 3 to 4 on Letter,
  "Where are my files?" from 9 to 12 and 10 to 12. A row that will not fit is
  moved down whole, which leaves the foot of the sheet before it blank. Every
  other card is unchanged.

## v4.1.3-beta.11

### New

- **Twelve more i1Pro charts.** Knut's 8 mm line-up is complete: the same eight
  patch counts on **US Letter** as on A4 (156 up to 3,432), an **A4-3432p** to
  finish the A4 run, and three on **A3 landscape** (1,144 / 2,288 / 3,432) laid
  out on a 44-column grid. Nineteen charts in all, grouped by paper in the
  preset list and climbing by patch count inside each group — you pick the
  sheet in your printer first.

  The Letter charts keep their own right and bottom margins (9 mm and 15 mm
  against A4's 6 and 19). That is deliberate: Letter is 18 mm shorter than A4,
  so it does not need A4's deeper bottom margin to keep a strip inside the
  i1Pro ruler's 240 mm travel.

## v4.1.3-beta.10

### Fixed

- **The 8 mm i1Pro charts printed without their ruler marks.** Knut, on the
  A4-2288p chart: *"the markers should be active so this is a bug. It was not
  intended."* All nineteen of his exports ask for marks on and five to a patch;
  the family's shared recipe said off and three, and because every chart in the
  family is built from that shared recipe, **all seven of them** lost the marks
  whatever their own export said.

- **The A4-2288p chart's stored setup rebuilt a different chart.** Its recipe
  described a nine-step colour cube where the chart was built with eleven, so
  "Load setup from preset" offered a design that regenerated other colours from
  the second row on. Knut re-exported it; the chart and its setup now match, and
  all 80 bundled charts regenerate their patch sets colour-for-colour.

## v4.1.3-beta.9

### Fixed

- **The folder guide's vertical lines now reach the folders they point at.**
  A folder whose explanation ran to more than one line had a gap between its
  own connector and its first child's, so the diagram read as dashed — below
  `run1/` and `verifications/` especially (Knut). Every continuation line now
  carries the level the row opens, and the top-level folder gets its own
  vertical for the first time. On screen, on paper, and in
  "Where are my files.txt".

- **The CMYK+N card's steps are a real numbered list.** They were literal
  characters — `1)` with no indent and sub-points at the same margin as the
  text around them. They now read `1.` `2.` `3.` with the text indented under
  the number and item 5's three sub-points as a proper bulleted list, on screen
  and in print alike, matching every other card (Knut). Still one printed page.

- **Opening the Tools menu with no project open could invent a project.**
  Asking where the working folder is was enough to make ChromIQ name one and
  keep the name, so the next action created a folder nobody asked for. It now
  asks whether a project is open, which creates nothing.

### Known

- The first-run sentence on the Profile-run bar is clipped at some window
  widths — three of its four lines at 1200 px, and at 900–1000 px its second
  line is drawn over the icons beside it. It has always been too tall for the
  space; it only became visible when the text stopped being invisible in
  beta.8.

## v4.1.3-beta.8

beta.7 fixed the loud half of a fault and made the quiet half worse. Both are
closed here.

### Fixed

- **Settings could follow you from one run to another.** ChromIQ marks the
  chart rows as "belonging to the build" while a chart is being made, so the
  run change the build itself causes cannot reset them. That mark was only ever
  taken down when a build FINISHED — so a Generate that was refused, that
  failed to estimate its patch count, or that you cancelled left it up, and the
  next run or calibration you clicked never received its own settings. On
  screen: a run with a 17 mm margin, a refused Generate, one click to
  Calibration, and the calibration showed 17 mm.

  beta.7 widened this without meaning to: before it, a stale mark suppressed
  only part of the panel; after it, all of it.

- **The "by Pharmacist" charts still rebuilt themselves as a different chart.**
  beta.7 said this was fixed and it was not — that family never claimed its
  rows at all. Pressing Generate once, changing nothing, turned TC3.00's 300
  bundled patches into 504, with no error to show for it.

- **Choosing "Default" left the previous preset's design on the run.** One
  click was enough to reproduce *"a previously created patch set setting is
  there instead"*: "Default" builds a fresh chart through targen and has no
  design of its own, but it said "leave the record alone" rather than "this
  chart has no design".

- **The first-run guidance was invisible** — black text on the black masthead
  (1.11:1 for the two labels, 1.55:1 for the sentence, where readable text
  wants 4.5:1). Both style hooks existed and nothing used them.

## v4.1.3-beta.7

### Fixed

- **The first "Generate Chart" after loading a built-in preset failed, or built
  the wrong chart.** On a fresh project, loading a preset and pressing Generate
  reported *"Nothing for targen to generate"* over an empty preview — with
  "Edit patch recipe (override preset)" untouched, and targen never involved in
  the preset at all (Knut).

  Loading a preset builds its own patch set and then moves the Profile-run bar
  onto the new run. On a fresh project that is a change of run, so the rule that
  opens an unvisited target on its defaults fired and reset the chart rows —
  and the factory default for "Total Patch Count" is zero. The preset's own
  binding no longer matched, so Generate abandoned the preset's patch set and
  fell through to targen. Rows that belong to the build on screen are now left
  alone; a genuine switch to another target still opens on its defaults.

  **On the "by Pharmacist" presets it was worse and silent**: automatic patch
  count is on there, so no error appeared and a different chart was built —
  TC3.00's 300 patches came out as 504, with no warning.

  This shipped in **4.1.2** and is not a beta regression; every 4.1.3 beta has
  it too.

## v4.1.3-beta.6

Knut's wording batch for the help cards, and the guard that should have been
there when the print sizes were fixed.

### Changed

- **Every help card names the thing it is telling you to click.** "the bar" is
  now "the Profile-run bar" — the name its own table gives it — in all nine
  places that said otherwise, and "card" is "help card" throughout, so a printed
  page still says what it belongs to when it is read away from the app (Knut).

- **Getting started ▸ "1. Create Chart"** now also points at the ready-made
  charts behind the "Built-in presets" button and at Tools ▸ Charts & patch sets
  ▸ "Edit / create chart patch set" for designing the colours yourself.

- **Getting started ▸ "3. Measure"** explains the overlay: "Each patch shows:"
  and its three choices, "Show only measured patches", and the progress bar
  above the preview.

- **"Open a project" is now the first entry** under "More than one way to do
  most things", and it names the file to look for — "project.json", inside the
  profile's own folder — or the folder itself.

All twelve translations updated with it, using each language's own names for
the controls it quotes.

### Fixed

- **Nothing was stopping the printed help cards going back to point sizes.** The
  comment in the print style sheet claimed a test guarded it; there was none,
  and the rule next door matches only margins. A font size in `pt` is resolved
  against the screen's DPI, which is what made the cards print a quarter smaller
  on macOS than anywhere else (fixed in beta.4). Reverting every size to `pt` was
  proven to slip through unnoticed; it now fails.

### Known

- The help-card body text is **14 px**, which measures as Times New Roman 11–12
  (x-height 1.914 mm against TNR 11's 1.774 mm). The Measurement Report's body
  is 12 px, below TNR 10 — that is the document that is genuinely small.

## v4.1.3-beta.5

### Fixed

- **A chart could carry a record of a design that never built it.** Knut spotted
  it from the outside — he took a 1,144-patch preset as a basis, built a
  different chart over it, and the stored setup data went on describing the old
  one; charts made from that chart inherited the same wrong record. He was
  right, and it reaches further than the exports he sent: these records live in
  your own saved Create Chart presets, so an affected entry offers the wrong
  design as the starting point for the next one in "Load setup from preset".

  Saving a chart's layout has always been allowed to leave its creation recipe
  alone, which is correct for a layout-only save. A REBUILD from a different
  patch set was doing the same thing, so nothing ever cleared the old design.
  There is now a third state — *this chart was not built from a stored design* —
  and loading a patch set uses it, so the previously selected preset's design
  is no longer stamped onto a chart it does not describe.

  Existing records are not rewritten: a chart already carrying the wrong design
  keeps it until it is rebuilt.

## v4.1.3-beta.4

Knut's help-card batch. Chasing a heading that printed on its own turned up the
reason: the rules that lay out a printed card were measuring a document they had
already destroyed, and pages of it were never reaching the paper.

### Fixed

- **Printed help cards were losing whole pages of text — silently, and on
  paper.** A `QTextDocument` lays itself out lazily, and changing a block in one
  that is only half laid out does not make the geometry stale, it DESTROYS it:
  every element below the change collapses to nothing. Each of the four
  pagination rules measures the document and then edits it, so each could trip
  it. The dictionary card printed **29 of its 79 entries**; the other 50 existed,
  paginated, and were simply not on any sheet. The card looked finished — it
  ended with a heading and a page number.

  This has been shipping. On US Letter the glossary has been losing its last
  entries since the rules were introduced; 4.1.3-beta.3 widened it to A4. Every
  rule now takes its layout from one place that finishes the layout first, and
  every card on A4, Letter and A5 has been read back out of the PDF word by
  word: nothing is missing.

- **Help cards printed a quarter smaller on macOS than anywhere else.** Font
  sizes were in `pt`, and Qt resolves those against the primary screen's logical
  DPI — 72 on macOS, 96 elsewhere. So 10.5 pt body text was 11 px on a Mac and
  14 px on Windows, Linux and in every test we ran, while the folder guide's
  directory tree kept its absolute 12 px and towered over the text around it
  (Knut, A2). Every size is now in `px`, so the printed page is the same
  everywhere and what the tests measure is what comes out.

- **A card title no longer wraps.** "Calibrate my printer (and how that differs
  from a profile)" ran to two lines. The `h1 { font-size: 19pt }` meant to
  control it was dead — Qt fixes an `<h1>`'s size from its own default and
  ignores the style sheet, inline styles, and every unit (measured). Titles are
  a styled paragraph now, and the longest one fits with room to spare (A3).

- **A section heading could print alone at the foot of a page**, its text
  overleaf — Knut's "Instrument" in the dictionary card (A5). The rule that
  exists to prevent this judged which page a block was on by the top of its box,
  and a block can start in the last pixels of a page while its first line falls
  on the next. It judges the line now. A second fault in the same rule abandoned
  every later heading in a card once it met one it could not move.

- **A blank line at the END of clip-border text now prints.** Leading and
  interior blank lines came back in beta.3; the last one was still swallowed,
  because `splitlines()` treats a final newline as a terminator rather than a
  separator (Knut). Putting a space on the line worked, but an invisible space is
  no answer — any editor that trims trailing whitespace throws it away.

### Known

- On US Letter, three cards still end with a page holding only the closing line.
  Their content is 2–4 % taller than a Letter page; no typographic rule fixes
  that, only shorter cards.
- A table row that meets a page break still stretches to the page bottom instead
  of ending under its last line (Knut, A1). Qt grows the last row on a page, and
  the honest fix is to split the table at each break — its own piece of work.

## v4.1.3-beta.3

The preview window beta.2 put in front of the print dialog is gone — and taking
it out uncovered the fault it had been showing all along.

### Fixed

- **Help cards printed at a third of their size on macOS.** ChromIQ asked the
  printer to work in the 96-dpi units the cards are written in. A PDF writer
  agrees to that; a printer does not — macOS snaps the request to a resolution
  the queue actually has (96 became 300 on both printers here) while still
  reporting its pixels at that resolution. Dividing those by 96 read a 180 mm
  page as 562 mm, so every card was laid out for a sheet three times too wide
  and then squeezed onto the real one: microscopic text crammed into the top
  third, and 3 times too much of it on each page. Every card, both common paper
  sizes. It reached only the printer — "Save as PDF…" came out the right size
  throughout, which is why nothing looked wrong until a preview drew the
  printer's page on screen. Cards now print at the printer's own resolution,
  and all 18 cards on A4, Letter, A5, A6, Legal, landscape and wide margins
  come out page-for-page identical to the PDF.

  Linux was not affected — its print engine takes the resolution it is given.
  Windows should not be either, for the same reason, but that has not been run.

  The saved PDFs shift very slightly with this: the printable width used to be
  rounded down to a whole device pixel and is now not, so the text column is
  0.35 mm wider. Page counts are unchanged on every card.

- **A help card could run to half again as many pages on US Letter.** Keeping
  table rows off page breaks put the break directly after a repeating header
  row, and Qt then had to reprint that header on the new page: one such break
  cost three pages. The folder guide finished at 14 pages on Letter where the
  same card on A4 took 9. It now moves the whole table down instead: 11 pages,
  with no row cut in half on any card at either size. A4 is unchanged at 9.

  Five other cards lost pages too, one of them eight. Letter still has one
  near-empty page in the folder guide, where a heading sits alone above its
  table — beta.2 had four.

- **Printing no longer changes the print job's settings.** Painting a card left
  the printer at 300 dpi even if the user had chosen 600.

### Changed

- **Print… opens your system's print window again, with no preview window in
  front of it.** ChromIQ cannot put a preview inside that window: on macOS the
  pane Apple draws there belongs to a kind of print job Qt does not use, the
  Windows print dialog has no preview at all, and Qt hides the one in its own
  Linux dialog. To see the pages before they are printed, use "Save as PDF…"
  beside the button.

## v4.1.3-beta.2

Knut's second batch, and it turned out to be one fault wearing several hats: the
printed Help cards were never being paginated, so almost everything he reported
about them had the same cause. Plus his seven new i1Pro charts, two withdrawals,
and the full translation pass.

### Fixed

- **Printed Help cards were laid out for a page ChromIQ never asked for.** The
  document was handed a text width instead of a PAGE, which sends Qt down a
  different path: it re-lays the card at the PRINTER's resolution and adds a
  2 cm margin of its own. Three of the reports follow from that single line.
  Every card printed into a 140 mm column on a 180 mm page. The folder guide's
  section headings and its whole directory tree came out as an unreadable
  smudge, because the cards are written in pixels and a pixel meant something
  different on a 720 dpi printer than on a 96 dpi screen — which is also why the
  same bug looked different to different testers. And the workflow diagram was
  clipped at the right edge and printed again on the next page.

- **Bullets and numbered lists printed as one continuous block.** Two causes,
  both now fixed. Qt's rich-text engine accepts a margin in pixels and silently
  ignores one in points, so a stylesheet written in points has no spacing at
  all — no blank line above a heading, no gap between list items, no indent
  under a dictionary term. And a card whose body is plain text (the CMYK+N one)
  was being pasted into HTML, where newlines simply vanish.

- **The steps named the wrong tab.** "Print an existing test chart" told you to
  go to Measure. The table of tab names was numbered from zero with four
  entries; the steps are numbered from one across five.

- **"Save as PDF" offered "Untitled.pdf".** ChromIQ now asks for the file name
  itself, with the card's own title filled in.

- **The Help window dropped behind the main window** after the print or save
  panel closed, so you had to reopen Help to get back to the card.

- **The ruler-marker warning was drawn on top of the strip labels and the
  dashes.** It now sits below the sheet, outside the page, centred — in a band
  reserved before the page is scaled, because the frame around a sheet that
  carries its own white margin can be zero pixels wide. Its wording is Knut's.

- **Keyboard shortcuts were spelled in macOS symbols everywhere.** ⌘1 is Ctrl+1
  on Windows and Linux, and the card now says whichever is true where you are
  reading it.

- **Blank lines in the clip-border text were dropped** at the first and last
  line. They are writing space, and they are all kept now, for every content
  option that takes text.

- **"Export template" wrote only the strip's measurements**, never the content
  you could see in the preview. It now exports what the preview shows for any
  content option; with the band switched off it still writes the blank,
  exact-size design canvas that button was made for.

### New

- **Every printed page carries the ChromIQ wordmark and the five-segment
  spectrum bar**, the card's name from page two on, and a page number centred on
  the page rather than tucked into the corner.

- **The printing rules Knut asked for**: a blank line above every heading, no
  heading stranded at the foot of a page away from its text, no table row cut in
  half by a page break, and a table that spans pages repeating its header row at
  the top of each one. They live in a module the Measurement Report shares, so
  it can adopt them next; today the report uses only the whole-table rule it
  already had.

- **Print… now shows a preview** before the system print dialog, which on macOS
  shows none of its own. *(Withdrawn in beta.3 — see above.)*

- **Seven new i1Pro charts** on A4 with 8 mm patches — 156, 312, 572, 1,144,
  1,716, 2,288 and 2,860 patches, one 22 × 26 grid, 572 to a sheet. Knut's own
  i1Pro charts are now listed in ascending order within their block, like the
  ColorMunki and i1Pro 3 Plus ones.

- **"Imported image" can carry text too.** Only the Notes box fills itself in,
  so only the Notes box switches the Text field off.

- **The strings this work added are translated in all twelve languages** — 40
  of them, with no English placeholders among them. (The catalogues as a whole
  are not finished: each language still carries roughly 25 long strings from
  earlier work that read as English. Those are on the list for GA.)

### Changed

- **Two built-in charts were withdrawn** at Knut's request: the i1Pro
  A4-495p-1page-Landscape, and the i1Pro A4 "TC9.24 by Pharmacist" that had been
  parked since its bundled page disagreed with its own reference. Nothing on
  disk points at a built-in preset, so **a project built from either one still
  opens, still reloads and still restores its used chart** — only the dropdown
  rows are gone. The ColorMunki A3 TC9.24 is a different chart and stays.

- **The clip band's fit and move fields now apply to the ChromIQ branding as
  well as to an imported image**, and they are the same stored fields — so a
  preset that carried an image placement applies that placement to branding too.

- The clip area reported in Preferences follows the paper of the recipe loaded
  there instead of always reporting A4.

- **Blank lines you typed into the clip-border text are now printed as you typed
  them.** A saved preset or recipe whose text begins or ends with blank lines
  will print a taller band than it did in beta.1. No bundled chart is affected —
  every built-in's clip text is four lines with no blanks.
- **"Imported image" now honours the clip Font and Size** as well as the Text.
- **The chart preview shrinks a little** while the marker controls differ from
  the sheet on screen, to make room for the caption underneath it.
- **No built-in preset is parked any more.** The greying mechanism stays; it
  simply has nothing in it.
- **Print… opens a preview**, not the system print dialog, and saving a copy is
  now its own button beside it. *(The preview was withdrawn in beta.3; the
  separate button stayed.)*
- **The i1Pro preset list is in a different order**, so entries you knew by
  position have moved.

### Known

- The seven new i1Pro charts are laid out with a **6 mm right margin**, while
  ChromIQ's own i1Pro seed asks for 9 mm — their other three margins match it
  exactly. They ship exactly as Knut authored them, so the Measured-from-Preview
  panel will flag the right edge on all seven until it is decided which of the
  two numbers should move.

### Internal

- `paginate_tables` moved from the Measurement Report into a shared
  `ui/pdf_layout.py`; the report keeps its behaviour and its tests.
- One of the seven imported presets carried a colour-set sidecar claiming 1,200
  patches beside a 2,288-patch chart — "Load setup from preset" would have
  offered to regenerate it 1,088 patches short. The importer now re-points the
  patch count as well as the instrument and paper, and a test pins it.
- `docs/dev_builtin_presets.md` gained the missing procedure for removing a
  built-in for good, and lost a false claim that Guided mode depends on one
  particular preset plus two citations of test files that do not exist.

## v4.1.3-beta.1

Knut's 2026-08-23 batch. The ruler helper markers turn out to have been right on
paper all along — it was the preview that was lying — and the clip-border panel
was dead on a ColorMunki. Help cards can now be printed.

### Fixed

- **The preview was counting two combs of ruler dashes at once.** Knut reported
  that "Markers per patch" drew five dashes when set to 4 and seven when set to
  6, unevenly spaced. The printed sheet was never wrong: the geometry draws
  exactly the number asked for, every gap identical, with the outer dashes
  centred on the spacers — the design he specified. What was wrong is what the
  screen showed. A sheet keeps the dashes it was *generated* with, and the live
  overlay drew the *current* spin-box value over the top, so the preview showed
  the union of the two combs: 3 printed + 4 proposed = 5 dashes per patch,
  unevenly spaced; 3 + 6 = 7. Every number he counted falls out of that. The
  overlay now says so — while the controls differ from the sheet in front of
  you, the dashes are drawn in the accent colour under the caption "Markers not
  on this sheet yet — press Generate Chart", and go back to plain black once the
  two agree. Dash positions are rounded rather than truncated, so the overlay
  lands on the printed ink instead of half a pixel below it, and the white halo
  narrows and then gives way when dashes are close instead of flooding the gaps
  between them.

- **The clip-border Preview and "Clip area" work on a ColorMunki.** They were
  dead for every content mode on a ColorMunki or SpectroScan preset — an empty
  box and a long dash — while the band was printed onto the sheet all the same.
  The panel built its geometry for an i1 or i1Pro 3+ and answered "no band" for
  anything else; it now asks the same question the renderer asks. A second cause
  went with it, and that one was never instrument-specific: the preview worked
  the band width out from the page margins rather than from the recipe, so wide
  margins erased the clip area on an i1 too. "Export template (PNG + PDF)" was
  behind the same guard and did nothing on those instruments.

- **A disabled text box now looks disabled.** The clip-border Text field is
  switched off in Notes-box mode — the notes design fills itself in — but it was
  pixel for pixel identical to a live one, so it read as editable and its
  contents looked ignored. Both themes were missing a rule for text boxes; the
  field's label greys with it now. The same box in ChromIQ-branding mode is
  live, and now visibly so.

- **"Also export a PDF" was exporting charts without their helper markers.** The
  TIFF had them, the PDF silently did not, and both come out of the same tick of
  Generate Chart.

### New

- **"Show markers for: Top/bottom · Sides".** Two tick boxes in Ruler helper
  markers, so the set you do not need is simply not printed — Knut: *"especially
  as the strip markers are the most useful for measuring."* The set you keep
  reaches into the corners as well: the corner trim only ever existed to stop
  the two sets colliding, and with one of them off there is nothing to collide
  with. Carried in the recipe, so it saves and loads with a preset, and if you
  leave both unticked the panel says plainly that nothing will be printed.

- **Help cards can be printed.** A Print… button on any open Help card opens
  your normal print dialog, which is also where "Save as PDF" lives — handy for
  the keyboard shortcuts, or a workflow to follow at the printer. Every card
  kind prints, the glossary and the step lists included, and the Getting-Started
  card keeps its workflow diagram.

- **ChromIQ branding can be placed.** *"For Imported image option, then there
  are fields to position the image. Why are those options not available for
  ChromIQ branding?"* — they are now, and they are the same fields. "Content
  fit" and "Content move" scale the wordmark and move it across and along the
  band, and your own lines under the wordmark move with it. Rotation stays an
  image-only transform, because the branding always reads up the strip and
  "Flip 180°" is how that is turned round.

### Changed

- **Every tick box in "Measured from Preview" has its own ⓘ.** There was one
  icon against the first of three, carrying a single explanation of the panel
  and of all three boxes at once. Each box now answers for itself, and the
  overview of the numbers sits on the numbers.

- **Worth knowing if you have your own presets.** The clip band's fit and move
  fields now apply to the ChromIQ branding as well as to an imported image, and
  they are the same stored fields — so a preset that carried an image placement
  will apply that placement to branding too. The "Clip area" figure for an i1 or
  i1Pro 3+ can also read slightly differently from before, because it is now
  worked out the way the renderer works it out; a clip template exported earlier
  was sized to the old number and is worth exporting again.

### Internal

- The printed Getting-Started card was clipping its workflow diagram at the page
  edge and repeating it on the next page, because the picture was placed at a
  fixed size instead of the page's. The size now comes from the printer the user
  chose, so it is whole on A4, Letter, Legal, A5, A6 and landscape alike — the
  first version of this fix worked on A4 only and left A5 exactly as it was.
- Scaling the clip branding to an extreme value crashed the panel outright
  (Pillow refuses a glyph that large). It is capped now, and a branding that
  cannot be drawn leaves the band blank instead of taking the window with it —
  which needed a second fix, because the handler that promises that called a
  logger the module did not have and raised `NameError` instead. The same
  missing logger sat behind the helper-marker handler, unnoticed since 4.0.0.
- The marker overlay rebuilds its geometry with the chart's own patch count, so
  a matching overlay really does mean "these are the dashes on the sheet".
  Without it an area-first chart could be described by a comb nothing like the
  printed one.
- The two "Show markers for" boxes are stacked rather than side by side: on one
  line they made the Ruler-helper-markers group the widest thing in Expert
  Options and drove the whole column into horizontal scrolling.
- A help card that cannot be printed now says so instead of doing nothing. (A
  cancelled print dialog still says nothing, which is the point of cancelling.)
- The clip area shown in Preferences follows the paper of the recipe loaded
  there, instead of always reporting A4.
- The preset round-trip test was comparing several fields against their own
  defaults, so a dropped one would have passed unnoticed. It now sets every
  field, and a new test keeps it that way.

## v4.1.2

A polish release. ChromIQ starts in about half the time, tabs switch the instant
you click them, and a long list of small frictions in Create Chart, Measure and
the in-gamut module are gone. Nothing about how charts are made, printed,
measured or profiled has changed.

### Changed

- **The app opens in about half the time.** Roughly 5.7 seconds to a usable
  window before, about 3.0 now. Four separate things were costing that: the
  splash screen spent a full second inside the toolkit waiting for something
  that never happened, four separate filters each had to look at every event the
  app produced, the tabs were styled twice because the window was built assuming
  dark mode before the real theme was known, and the tab strip was restyled two
  or three times over with identical values.

- **Switching tabs is no longer sluggish.** Clicking a tab took about a quarter
  of a second before the tab appeared; it is now under a hundredth. The thin
  line under the tab bar was drawn in the current tab's colour, so every switch
  re-drew every control in all five tabs — around 26,000 of them.

- **Patch sample area is limited to what your patches can actually give.** On a
  chart with six-sided patches the area ChromIQ reads runs out of room sooner
  than it does inside a square one, and the neighbouring patch is flush against
  it — so a reading area a little too large picks up the colour next door on
  every patch at once. ChromIQ now works the limit out from the shape of your
  own patches instead of leaving you to guess. Square patches are unaffected.

- **Guided mode says what it keeps fixed**, and no longer applies settings you
  cannot see. Options Guided does not offer can no longer be stored by "Save as
  Defaults", and "Patch-by-patch mode" is now available there.

- **The ruler helper markers moved into Create Chart**, next to the chart they
  belong to, with a "markers per patch" control.

### Fixed

- **Create Chart no longer loses what you built with.** Pressing Generate could
  put the tab back into Manual with a different instrument, paper size and
  layout — whatever that run had stored from an earlier session — moments after
  your chart appeared. What the chart was built with now stays on screen.

- **Reading a chart with a scanner no longer gives up on six-sided patches.**
  When you place the four corners yourself, ChromIQ no longer asks the scanning
  step to work the perspective out as well; it never used that answer, and on a
  honeycomb it collapsed and took the whole scan with it. Nearly one scan in
  four failed or hung; now none do, and every colour comes back identical.

- **The in-gamut chart no longer offers colours your profile cannot print**, and
  a profile that can print nothing no longer gets the largest chart. It also
  starts from the chart you set up in Manual, and opening a run is quicker.

- **Your Measure settings stop changing when you switch runs**, and settings
  saved before this release still work.

- **Guided says which measurement options belong to Manual.** "Don't save
  spectral data" is one of them: Guided never applied it, but it looked as
  though it might. Guided still saves spectral data — it now says so instead of
  leaving you to wonder.

- **The chart preview no longer draws a white border twice.** Charts from the
  layout engine carry their own paper margin and the preview was adding another,
  so the sheet looked as if it had a wider white edge than it has.

- **Dialogs opened from a tab no longer borrow that tab's colour.** The
  measurement report showed a pink trend line opened from one tab and a green one
  from another, and in light mode those dialogs were missing the frame they have
  everywhere else.

- **The log text no longer stays bold after switching to dark mode.**

- **"Show overlay from existing measurement" explains itself** when there is no
  measurement to show.

- **The clip border prints its ChromIQ logo and your own lines together**, and
  its preview shows the size it will actually print.

- **On a machine without ArgyllCMS, the "not found" message is reachable and
  correct.** It could open behind the start-up picture with no way to reach it,
  and it gave every user macOS instructions regardless of their system.

### Notes

- Two switches are available if the new start-up behaviour ever misbehaves:
  **Classic splash screen** in Preferences → Beta, and the environment variable
  `CHROMIQ_SEPARATE_FILTERS=1`.
- Hexagonal charts in the scanner and camera tools remain opt-in under
  Preferences → Beta. A sample pack is attached to the beta releases for anyone
  who wants to try them.

## v4.1.1

### New

- **A set of 24 built-in charts for the i1Pro 3 Plus**, made and measured on
  paper by soul-traveller — the same treatment his ColorMunki charts had, for
  the other instrument. There is a size for every job: 84 patches on one sheet
  up to 2,016 across six A3 sheets, on A4, US Letter and A3.

  Pick one under **Create Chart → Manual → Presets**, or from the magenta list
  button next to the GUIDED / MANUAL switch, where they have their own
  **i1Pro 3 Plus** section. They are kept apart from the i1Pro charts on
  purpose: these layouts are cut for the 3 Plus.

  Every chart leaves a 40 mm run-in at the top so the instrument clears the
  first patch, 20 mm of white paper at the bottom to finish a strip on, and a
  28 mm band down the left for the instrument to run up before it reaches the
  first patch — the chart's details are printed in that band for you. Patches
  are 16 mm wide, except the two 84-patch quick charts, which use 25 mm.

  The colours are fixed, but the layout is not: change the paper, the margins or
  anything else and press **Generate Chart** to re-flow the same patches.

### Changed

- **The preset lists now name each instrument group the way the Instrument field
  does.** The headings in the **Presets** dropdown and in the ★ overlay used
  short names — "ColorMunki", "i1Pro" — which hid who the charts are for: the
  i1Pro charts suit an i1Pro 2 and an i1Pro 3 as well. The headings now read
  **ColorMunki / i1Studio / ColorChecker Studio**, **i1Pro / i1Pro 2 / i1Pro 3**
  and **i1Pro 3 Plus**, exactly as the Instrument box lists them, and the
  dropdown shows a proper heading above each group instead of only a dividing
  line. Chart and folder names are unchanged.

### Internal

- The importer that stages Knut's exported charts is now family-driven
  (`scripts/import_knut_presets.py <family> <folder>`), so a future line-up is a
  table entry rather than a second script. It still rejects any export that
  differs from its family's shared recipe outside the fields one chart may own,
  and re-points the colour-set recipe at the chart it actually built — which all
  24 of these needed.

## v4.1.0

Everything reported against 4.0.0 and 4.0.1 by soul-traveller is fixed — verified
by him on real hardware — and two features he asked for are in. The ColorMunki
also gains a complete set of ready-made charts, which he made and measured on
paper himself.

### New

- **A new set of 45 built-in ColorMunki charts**, made and measured on paper by
  soul-traveller. They replace the older ColorMunki charts of his, and are built
  for reading with a ruler: the margins keep the knobs under the instrument off
  the edge of the page, leave white paper to finish a strip on, and keep both the
  first and the last strip reachable. The helper markers are switched on, and at
  the ~10 mm patch width most of them use, the ruler goes four markers below the
  strip you are reading.

  Pick one under **Create Chart → Manual → Presets**, or from the magenta list
  button next to the GUIDED / MANUAL switch. There
  is a size for every job — 84 to 2,280 patches on A4, US Letter, A3 and A3+, in
  portrait and landscape. Most sizes come as a **Fast** and a **Slow Reading
  Speed** pair: same patches, but the fast one puts shorter strips on more sheets,
  because the ColorMunki reads a short strip more quickly. Three **Hand Held**
  charts use big 26 mm patches for reading without a ruler at all. Each chart
  prints the reason for every margin down its side, so the sheet explains itself.

  The colours are fixed, but the layout is not: change the paper, the margins or
  anything else and press **Generate Chart** to re-flow the same patches.

- **Ruler helper markers on the printed chart.** Short dashes along all four
  edges of the sheet, so you can lay a ruler against the paper and line your
  instrument up with the patches. One dash sits exactly at the centre of each
  patch and the next midway to its neighbour, evenly spaced all the way along —
  and they follow your patch spacers automatically, however you set them. Switch
  them on under the preview with **"Show helper markers"**, choose how far in
  from the edge they sit and how long they are, then press **Generate Chart**.
  The corners stay clear, and charts with six-sided patches grey the option out
  and say why.

- **A measurement progress bar in the preview header.** While you measure, the
  header fills in your accent colour and shows how far through the chart you
  are, so you can see progress without counting strips. Turn it off in
  **Preferences → Measurement** if you prefer the plain header.

- **Preferences → Sounds: "Wake the audio device before playing a sound".** Off
  by default. Turn it on if the first sound after a silence is too quiet or
  seems to start halfway through.

### Fixed

- **Measurement sounds work again.** An attempt to make the first sound louder
  could stop every sound instead — during a measurement, on the instrument
  button, and on the Play buttons in Preferences. ChromIQ no longer touches the
  audio device before playing, and the behaviour that caused it is now the
  optional setting above.

- **ArgyllCMS's own beeps play again**, alongside ChromIQ's sounds rather than
  instead of them. They are separate cues: the reader's beep tells you the
  instrument is ready for you to start, which none of ChromIQ's sounds covers.

- **Your Measure settings are saved when you press Start Measurement.** Anything
  you changed just before measuring — "Skip initial calibration", patch-by-patch,
  the tolerance, resume — was not being stored, so it reverted afterwards. Every
  control on that panel is now kept with its own run.

- **"Refine / resume existing measurement" no longer breaks a measurement when
  there is nothing to resume.** Ticking it on a run whose measurement is missing,
  empty or damaged made the measurement fail before the first patch. The tick is
  now honoured only when there really is a measurement behind it.

- **A chart with no measurement no longer claims its measurement belongs to a
  different chart**, and says plainly that it has not been measured yet.

- **"All strips read" waits until every patch really is read**, instead of
  appearing on a chart that is 97% measured, and the log says how many patches
  are still missing.

- **"n" during patch-by-patch reading moves to the next unread patch** instead of
  stopping on the one you are already on.

- **The ColorMunki's patch limit and the reading-speed guidance** now match what
  the instrument and the paper actually allow.

- **Loading a .ti1 in the patch editor** no longer adds more patches than the
  file contains.

- **A fixed seed reproduces the same chart** when a target is duplicated.

- **"Show helper markers" now follows the chart you load.** Opening a preset or a
  saved chart that uses the markers built them onto the sheet correctly, but left
  the tick box under the preview showing off. The tick box and the two distances
  now match whatever chart is loaded — and the two distance boxes are the same
  slim size as the margin boxes in Create Chart.

- **The live preview no longer replaces a chart you have just built.** With
  "Update the preview automatically" on, choosing a preset could show the right
  chart and then, a second later, replace it with one laid out the old way — the
  same patches, but narrower. A chart's own settings were not being filed against
  its run when it was built, so the run's previous settings loaded back over the
  screen and the preview redrew the sheet from those. Building a chart now saves
  its settings with its run straight away, and the preview follows the chart in
  front of you.

## v4.0.1

Fixes around the very first chart of a new project — found by Knut and
Sebastian testing side by side on one afternoon, all sharing a single root:
what you type before the first Generate had nowhere to live yet — together
with a group of measuring aids that were describing the chart slightly
inaccurately.

### Fixed

- **"Close to the limit" is only said when a strip really is close.** While you
  measure, the message under the chart preview tells you how your reading speed
  is doing. It was calling a strip "close to the limit" when it was as much as
  35% clear of it — so a ColorMunki strip read at 521 ms per patch was warned
  about even though the limit is 400 ms. How close is close enough to mention
  is now yours to choose, in **Preferences ▸ Measurement ▸ Close to the
  limit**, and it starts at 10%. At that setting the 521 ms strip in the report
  is simply called a good reading speed, which is what it was. Set it to 0% if
  you would rather only ever be told when a strip is genuinely too fast
  (reported by soul-traveller).

- **The reading-speed message now tells you the whole-strip time as well.**
  Milliseconds per patch is a hard thing to picture while you are holding an
  instrument. The message now also gives the figure you can actually feel — the
  seconds a whole strip should take — so instead of just "400 ms or more per
  patch" you get "400 ms or more per patch — 6.0 sec. or more per strip". If
  the window is narrow the message wraps onto another line and the area grows
  to fit it, rather than cutting the end off (reported by soul-traveller).

- **The ColorMunki gets more room at the top of the page.** The top margin
  ChromIQ warns below is now 33 mm for every paper size, instead of 30 mm. The
  reason is mechanical rather than optical: the two knobs on the underside of a
  ColorMunki catch on the edge of the sheet as you start a strip, so the
  instrument needs a little more paper in front of the first patch than the
  light path alone would suggest. If you had already set a margin of your own
  for a page size, your value is kept exactly as it is (reported by
  soul-traveller).

- **Loading a patch set tells you how many patches arrived.** The **Edit /
  Create Chart Patch Set** window now says, for example, "Loaded MyChart.ti1 —
  2002 patches", so you can check the number against the file you chose
  (reported by soul-traveller).

- **A chart keeps the patch set it was built from.** If you built a chart from
  a patch set of your own — one you made with the patch generators, edited in
  the Patch Set editor, or loaded from a file — and later pressed **Generate
  Chart** again, ChromIQ could quietly build a completely different chart with
  a fresh set of patches. It happened once the project had been closed and
  opened again, which is easy to do without thinking about it: the link between
  the chart and your patch set was only remembered while the app stayed open.
  This mattered most when the chart had already been printed, because the
  sheets on your desk then no longer matched the chart ChromIQ would measure
  them against, and nothing on screen said so. A run now keeps its own patch
  set, so generating again lays out the very same patches. Changing something
  that defines the patch set itself — the patch count, the grey steps, the
  white or black patches — still gives you a fresh chart, because that is what
  asking for different patches means. You can also see that your patches are
  protected: the **"Edit patch recipe (override preset)"** box is shown with
  the patch settings greyed out behind it, and you tick that box on the
  occasions when you do want a brand-new set of patches (reported by
  soul-traveller).

- **Loading a patch set no longer adds patches that are not there.** In **Edit /
  Create Chart Patch Set**, choosing **Load Patch Set…** and picking a `.ti1`
  file added more patches than the file contains — 2019 instead of 2002 for a
  typical chart. A `.ti1` file holds three tables, and only the first one is
  the patches to print; the two after it hold reference values that ArgyllCMS
  needs, such as the corners of the colour cube. Those were being read in as
  though they were patches. Only the patch table is loaded now (reported by
  soul-traveller).

- **The colour list handed to a print shop is no longer empty.** Every chart
  writes a `-colours.txt` file into its run's `exports` folder — a plain list
  of the chart's colours you can pass to a print shop or another program. That
  file was being written completely empty, for every chart, because of the same
  misreading of the three tables described above. It now contains the full list
  of colours again. Any file you exported before this will still be empty, so
  generate the chart again if you need one of them.

- **The measurement sounds are heard again.** Many of the short sounds went
  missing entirely — the tick for each patch, the thump for a patch that is
  off-colour, and ding, click, chime, buzz, bump and ding-hi — and longer ones
  could lose their opening, which is what stopped the bell sounding like a
  bell. The sound files were never at fault. On a Mac the sound hardware is
  allowed to go to sleep when nothing has been played for a while, and whatever
  wakes it up loses its own beginning while the hardware starts. A short sound
  can be over before the hardware is properly awake, so it is never heard at
  all. ChromIQ now wakes the sound hardware quietly in advance — when a
  measurement starts, and when you press **Play** in **Preferences ▸ Sounds** —
  so the sound you actually want to hear arrives into hardware that is already
  running. During a measurement the cues follow each other closely enough to
  keep it awake by themselves (reported by soul-traveller).

- **The instrument's own "ready" beep is back.** When you press the button on
  your instrument to start reading, it plays a short beep to tell you it is
  ready for you to move. That beep comes from ArgyllCMS rather than from
  ChromIQ's own sounds, which is why it does not appear in the list on
  **Preferences ▸ Sounds** — and it had gone quiet on macOS. It sounds again
  (reported by soul-traveller).

- **Three sounds start out better chosen.** A patch that reads off-colour now
  starts as **bump**, a finished measurement as **chime-long**, and a finished
  profile as **applause**. If you had already chosen your own sound for any of
  these, your choice is kept exactly as it is (chosen by soul-traveller).

- **The pointer ruler measures the chart you are looking at.** With "Show
  measurement coordinates on pointer" ticked, the readout used the Resolution
  setting rather than the resolution the chart on screen was actually made at.
  On a 200 dpi chart every reading came out at two thirds of the truth — an A4
  sheet's far corner read 140.0 × 198.3 mm instead of 210 × 297, and the ruler
  disagreed with the margins listed right below it. Both now read the page's
  own resolution, so they always agree, on any paper size and either
  orientation (reported by Knut).

- **The expected-vs-measured overlay sits exactly on its patches.** During a
  measurement the coloured split could leave a thin rim of the real patch
  showing along an edge. Four separate causes, all fixed: the patch boxes were
  rounded in a way that shifted them up and to the left; on a hexagonal
  SpectroScan chart the honeycomb offset was missing entirely; on a Retina
  screen an edge could land half a pixel off; and the strips were not always
  kept inside the page. The corrected patch rounding also makes the patch
  boxes in a scanner or camera target exact for rectangular charts. Scanner
  and camera work stays unavailable for hexagonal SpectroScan charts, as it
  always has been — a CHT recognition file cannot describe a hexagon, so
  those charts are measured with the SpectroScan itself.

- **The overlay legend keeps clear of the chart.** It could overlap the last
  row of patches, the edge spacer or the scan arrow, depending on the layout.
  On a ColorMunki chart with staggered strips it sat across the last patches
  of the lower strips: every second strip is offset down the page, and its
  recorded position did not include that offset. The strip highlight and the
  click-to-jump target on the Measure tab were off by the same amount on those
  charts, and are now exact.

- **"No spacers" now means bare paper.** Choosing no spacer still drew black
  bars between the patches and the strips; the gaps are left blank, as asked
  for.

- **Your run description survives the first Generate.** Typing a description
  for a brand-new project and pressing Generate Chart cleared the field and
  lost the text; it is now written into the freshly created run, exactly as
  it already was when adding a run to an existing project.

- **The project name is one value in Guided and Manual.** A name typed in
  Guided now appears in Manual immediately (and the other way round) — before,
  the two fields only agreed once a project existed, so a fresh start showed
  the name in one mode only.

- **The first chart of a new project keeps your settings.** After the first
  Generate, the screen could snap back to factory defaults — the instrument
  jumped from ColorMunki to i1Pro by itself, and a re-layout could redraw the
  chart with the wrong instrument's geometry, leaving the page half filled.
  A new project's first run is now born with the exact settings its chart was
  built from.

- **Save as Defaults no longer stores the project name.** Every other row on
  the tab is a preference; the name identifies a project — saving it seeded
  every future fresh start with an old project's name, one Generate away from
  building into it. The saved name from older versions is cleared too.

- **The app no longer crashes when an instrument keeps dropping off the USB
  bus.** Closing Read Single Patches now lets go of the measuring engine
  properly. Before, a session that ended by itself could report back a moment
  later, into a window that had already closed, and the app died outright
  (reported by Knut with a ColorMunki on a 2019 MacBook).

- **"No instrument found" now names the likeliest cause and offers the fix.**
  On some computers, older Macs in particular, the "Faster instrument
  connection" shortcut is what stops an instrument being seen at all. Both the
  measurement window and Read Single Patches now explain this and carry a
  **Turn off faster connection** button, so you do not have to go hunting
  through Preferences in the middle of a measurement; the text also says where
  the option lives (Preferences ▸ Measurement) for switching it back on. The
  option's own help text says when turning it off is the right move.

## v4.0.0

> **This entry covers everything that changed since v3.14.7, the last stable release** — 224 betas' worth of work, grouped so you can find what affects you instead of reading a diary. The individual beta histories remain in the repository.

**If you only read one paragraph:** ChromIQ 4.0 looks after your work — every
run keeps its own chart, measurement and settings, nothing you made is ever
deleted, and checking how good a finished profile really is has become a
guided, honest, repeatable workflow. Your existing projects are picked up
exactly as they are: ChromIQ migrates them in place the first time it opens
them, keeps every old file, and there is nothing you need to do first.

Two headlines in more detail. **ChromIQ now keeps track of your work for
you**: a profile run
holds its own chart, its own measurement, its own settings and its own
description; nothing you made is ever deleted, only archived; and every window
that could cost you something says exactly what it is about to do. And
**checking a finished profile is now a first-class workflow**: three clearly
explained ways to verify, honest statistics for each of them, and a
measurement report that keeps the whole dated history of a profile's health.

*(New words along the way — "gamut", "drift check", "judged as measured" —
each have a plain-language Dictionary entry: open the Welcome window's
"Dictionary and terminology" card. The card "Check a finished profile
(verification run)" walks the whole workflow step by step.)*

### New

**🎯 Verification, from start to finish:**

- **Three ways to check a profile, clearly told apart.** A chart built from
  the profile's own gamut (the everyday accuracy check), a chart printed
  through the profile (the strict whole-path check), and a sheet printed from
  your own application with the profile applied (the everyday-chain check).
  The Dictionary entry *"Which verification should I use? (the three ways)"*
  compares them, and the report records which way every sheet was made so
  they are never mixed silently.

- **A verification chart built from your profile's own gamut.** The **FROM
  PROFILE GAMUT** module on Create Chart asks the profile which colours it
  can actually print — from a fixed, published reference set — and builds the
  chart out of exactly those, so no patch is wasted on a colour that was
  never possible on this paper. White, black and evenly spaced grey steps
  take about one patch in eight — enough of a grey wedge to catch a
  drifting printer, without swallowing a small chart. Repeated checks of
  one profile always get the same colours, so this month's figures compare
  patch by patch with last month's. The chart already carries the profile, the Print Chart tab selects
  Raw for it by itself, and for a verification run with a built profile this
  module is the one Create Chart opens on.

- **A verification chart can be printed THROUGH its profile.** The Print
  Chart tab's **Colour** row chooses "Through the profile" (ChromIQ converts
  every patch itself — the printer's own colour management stays off, so
  nothing is ever converted twice) or "Raw — no profile". The choice, the
  profile file and the rendering intent are written into a print record
  beside the chart, and the report states them for every sheet.

- **Sheets ChromIQ did not print are asked about, once.** Measuring or
  importing a verification sheet that has no print record raises *"How was
  this sheet printed?"* — Raw / With colour management / Not sure (always
  safe, stores nothing). The answer is kept with that one measurement.

- **Import a measurement made in another program.** With **Run type** set to
  **Verification**, the Measure tab shows an **IMPORT** module (it exists
  only for verification runs): it files an i1Profiler (or any .ti3)
  measurement as a dated verification — converted, checked patch-for-patch
  against this run's chart, and stored exactly where a native measurement
  would go. Your original file is never touched.

- **The report judges every sheet by the fair yardstick.** A print that
  mapped white to the paper — through the profile with relative intent, or
  another application's colour management — is judged **relative to its own
  paper white**; everything else is judged **as measured — no white
  adjustment** (a way of comparing, not a rendering intent). The report says
  which was used, per sheet, and physical readings like paper white and
  deepest black always stay as measured.

- **Colour accuracy is split into within / beyond the profile's gamut.**
  Some design colours are simply not printable on a given paper; their
  distance describes the gamut, not a mistake of the profile. The report
  shows both groups — side-by-side columns in the detail chapters, row
  blocks in the Overview so dated columns stay comparable — and Pass/Fail
  judges the within-gamut figures. Every patch stays counted and visible.

- **Raw sheets get a drift figure instead of an unfair verdict.** A sheet
  printed raw is not expected to match the design, so it is never graded
  Pass/Fail against the profile thresholds. Instead the report compares it
  with your **previous raw check of the same chart** — print against print,
  patch by patch. The first raw check becomes the baseline; checks made with
  different charts are refused rather than mispaired.

- 📈 **The Measurement Report grew into the profile's health record.** It
  gathers every dated check of a run automatically, trends colour accuracy,
  paper white, darkest black and the cube corners over time, lets you
  untick individual runs, warns about mixed instruments and mixed printing
  methods, carries adjustable Pass thresholds, and remembers every option
  you set. **Save report as PDF** produces a print-sharp document (vector
  text, ~300 dpi charts) whose proposed folder always matches what the
  report covers — one dated check, one run's checks, or the whole profile.

**🧰 And the rest:**

- 🧭 **The run bar — one place that says what you are working on.** Above the
  tabs, on every tab: **Profile run**, **Run type** (Profiling,
  Verification — and Calibration, once its options are enabled in
  Preferences) and — for verifications — which dated check,
  each with its own ⓘ explanation. Beside them sit the run actions:
  duplicate a run, restore the chart a measurement was made with, and
  delete — with a window first that says exactly what would happen. The
  whole app follows the bar: Create Chart, Print, Measure and Build Profile
  always show the run it points at, and when no project is loaded the bar
  says so instead of guessing.

- 📦 **Ready-made Red River Paper charts.** Four built-in starting points in
  Create Chart carry Red River's own 2052-patch Standard Patch Set v25 —
  byte-identical to their published file — laid out and verified for i1Pro
  (A4 and Letter, with the clip-border record) and ColorMunki. The patch
  set is fixed so results stay comparable; every layout control (paper,
  margins, branding) stays yours to change.

- **Every setting belongs to the run you set it on.** Create Chart, Measure
  and Build Profile each remember their own settings per run — and per run
  type, verification included; switching run, opening a project or changing
  run type loads them, leaving a tab saves them — without a dialog. This
  holds before any chart exists, and a generated chart's own file records
  the complete recipe that made it, so returning to a run always shows the
  options its sheet was really built with. A brand-new run starts from the
  values of the run you were on — by design, so "make another run like this
  one, with one change" needs no preset.

- **Runs have descriptions.** "Matte paper, second attempt" appears in the
  run bar, the measurement report and on the printed chart
  (`{rundescription}`); verifications and the calibration have one too. The
  profile description writes itself from project, run and date — editable,
  or off. And the installed copy of a profile can be **named after its
  description** (a checkbox on Build Profile), so the profile picker in your
  editor reads like your own words.

- **Calibration is a run type.** Once **"Enable calibration options"** is
  ticked in Preferences, **Calibration** appears in the Run type list —
  choose it and the whole app follows: chart, measurement, `.cal` file and
  its description live in the project's `cal/` folder, shared by every run,
  and each profile run records which calibration it was built with — one
  run can keep an older calibration with "Include" while another applies
  the new one.

- 🔔 **Sounds during measurement** — a strip accepted, a patch misread, a
  session finished — so you can keep your eyes on the chart. **Preferences →
  Sounds** — pick a sound per event, or point ChromIQ at your own sounds.

- **A gentle warning when you swipe a strip too fast.** Every instrument
  takes a fixed number of readings per second, so a strip has a minimum
  time it needs — swipe faster and patches get too few readings, even when
  ArgyllCMS still accepts the strip. ChromIQ knows the pace for your
  instrument, shows a live verdict while you measure, and mentions it when
  a strip was read quicker than the minimum, so you can re-read it before
  it costs you accuracy — the strip reading times under the chart preview
  mark such a strip with an **✕**. Tune or switch it off under
  **Preferences → Measurement** ("Warn me when I read a strip too fast").

- 📖 **The "Getting started" help card was rebuilt**: a clickable chapter
  index, chapters that walk from first start to a finished profile, its own
  chapter on checking a finished profile (the three ways, and which to
  pick), and a plain-language overview of where your files are stored — in
  all twelve languages.

- 🌍 **Twelve languages, complete** — German, Spanish, French, Italian, Dutch,
  Portuguese, Swedish, Norwegian, Polish, Russian, Japanese and Chinese —
  every button, message, tooltip and help text.

- **Demo projects for learning and testing**, attached to this release as
  downloads:
  [ChromIQ-demo-projects.zip](https://github.com/itsab1989/ChromIQ/releases/download/v4.0.0/ChromIQ-demo-projects.zip)
  demonstrates the file-handling rules step by step (including projects in
  the old 3.13 layout, to watch the migration happen),
  [Demo-Report-Matrix.zip](https://github.com/itsab1989/ChromIQ/releases/download/v4.0.0/Demo-Report-Matrix.zip)
  holds thirteen documented Measurement Report cases with one ready-made
  PDF per case, and
  [ChromIQ-Switching-Demo.zip](https://github.com/itsab1989/ChromIQ/releases/download/v4.0.0/ChromIQ-Switching-Demo.zip)
  demonstrates the per-run settings rules with documented test cases.

- **Preferences → "Hide the log panel on every tab"**, for when the chart
  preview deserves the room. The full log is still written to disk.

### Changed

- **The ChromIQ layout engine is the default for new charts** — in Manual
  mode too, where printtarg stays one untick away (Guided has used the
  engine all along). A saved echo of the old off-default is migrated once;
  a choice you make yourself is never touched, and charts that exist keep
  the layout recipe recorded in their own file.

- **The chart-reading engine has left the Beta tab.** It and its
  companion options (patch flagging, calibration retries, faster
  connection, the misalignment warning) now live at the top of
  Preferences ▸ Measurement, and the engine no longer carries a beta
  label — only the profile engine is still experimental.

- **The measurement report explains its own limits.** *How to read this
  report* now says what the one ΔE figure bundles — the profile's
  conversion of each colour, the printer's behaviour on the day, the
  instrument's own small uncertainty — and points to Check & Refine ▸
  **Analyse Profile Quality** as the check that looks at the profile
  alone. It also says plainly what the figures are for: comparing a
  profile with itself over time, not ranking papers or printers against
  each other. The coverage line in Create Chart and the report's
  within-gamut note now carry percentages besides the counts.

- **Preferences links the ChromIQ website.** The "Created by" line above
  the buttons carries a **Website** link in the app's accent colour — one
  click to the showcase page.

- **The measurement report breathes, and its PDF prints the same
  everywhere.** A small gap under every section headline, after the intro
  lines, and between the four trend charts; each section starts on its own
  PDF page, and a table always keeps its headline beside it. Headline sizes
  are pinned, so a saved report renders identically wherever it is made.
  The report window opens a little wider, and the console warning about a
  missing "Sans-serif" font is gone.

- **The measurement model is consistent everywhere.** Replacing a chart,
  rebuilding one, measuring over an existing measurement, deleting a run —
  each has one window, one wording and one outcome, whichever tab you reach
  it from. The rules live in `docs/design/` and the app is tested against
  them.

- **Nothing is deleted, only archived.** Replaced measurements, regenerated
  charts, redone calibrations and replaced verification charts all move to a
  dated `old/` folder — and the windows say so before you commit.

- **Every measurement keeps a copy of the chart it was measured with**, saved
  the moment measuring starts — profile runs, dated verifications and the
  calibration alike — and **Restore Used Chart** puts it back. A dated
  verification is always judged against the chart *it* was measured with,
  even if the shared chart was replaced later.

- **File dialogs are ChromIQ's own everywhere** — with the sidebar shortcuts
  to your working folder — instead of the bare system dialogs.

- 🗂️ **Existing projects are migrated in place.** A project from 3.13 or an
  earlier 3.14 is reorganised into the new folder shape the first time it is
  opened — every old file kept, the plain-language folder guide ("Where are
  my files?" in the Welcome window) always current.

- **The interface holds still.** Buttons sit in the same place on every tab,
  the log panel ends on the same line shown or hidden — and can be dragged
  as large as the window allows — the run bar no longer shifts during
  start-up, and windows placed off-screen by the system are nudged back so
  their bottom row of buttons is always reachable.

- **The icons were drawn for the job.** Load Project and Load chart have
  their own recognisable icons, the Duplicate and Calibration actions got
  purpose-made marks, and the run bar's action marks were aligned optically
  — reviewed on screen, in light and dark mode, before being adopted.

- **The windows that ask what to do with a chart read like every other
  window** — explanation in plain text, buttons in a row, Cancel set apart,
  long project names shortened in the middle with the full name given in the
  text.

- **ChromIQ starts a little quicker** — the printer list is fetched when you
  first open Print Chart rather than while the window is being built.

### Fixed

Two hundred and twenty-four betas fixed far more than fits a list — the
per-beta histories in the repository carry the complete record. What users
met most sat in measuring and in chart handling, so those come first:

**While measuring:**

- **Pressing Esc during a measurement no longer throws your readings away.**
- **Patches no longer come back as "inconsistent" for no visible reason** —
  the tolerance sent to the instrument was stricter than the manufacturer's
  own default.
- **Several measurement windows never appeared at all** when the ChromIQ
  reading engine was in use — the abort confirmation, failure windows, and
  two that opened in silence. All reachable now, verified against a real
  instrument, and the sound tables for every window are written down as
  specification.
- **A resume no longer archives the measurement it resumes from**, a
  finished re-measurement of a whole chart announces its completion, and a
  good measurement is no longer called foreign while guided refinement
  loses its ticks.
- **The "this chart already has a measurement" window opens showing what
  the panel actually says** — its old answers could quietly switch an armed
  refinement off and turn the next read into a replacement.
- **"No instrument found" fired once per app run** instead of every
  attempt, and the abort window wording was reworked.
- **Text typed for a "New run" is kept**, and lands on the run you make.
- **The strip reading times sit exactly under their strips** — they used to
  drift right of their strips as the preview re-fitted; they are placed
  live at every paint now, and on a small window they split into two
  staggered rows so every time stays readable.

**Charts and previews:**

- **"This chart was made for a different instrument" could name the wrong
  instrument** — it compared your connected device against a setting rather
  than against the chart itself.
- **Restoring a calibration chart put back a completely different chart**,
  and a calibration restore redrew the selected run's chart.
- **The chart patch-set editor and the 3D patch view opened the run's
  chart, not the chart you had selected.**
- **The windows that ask what to do with a loaded chart were rebuilt** —
  explanation in plain text, buttons on one row, Cancel set apart, long
  project names shortened without clipping ("JSE AS BASE FOR A NEW
  PROFILE" is gone: windows widen to fit their buttons, everywhere).
- **The auto-update preview judged the wrong chart** after switching
  modules, and a switched-off option now looks switched off in both
  themes.
- **printtarg margins were applied in the wrong order** (top/right/bottom/
  left confusion) — charts now sit where the instrument minimums say.

**Reports, projects and the app around them:**

- **Checking for updates works again for stable versions.** The check used
  to fail with "No release tag found" whenever the newest releases were all
  betas; it now asks for the latest finished release directly.
- **The measurement report's PDF paginates cleanly** — headings stay with
  their tables, the trend legend never overlaps the graph, and charts print
  sharp instead of pixelated. The proposed save folder follows the
  four-location design again. The report window itself keeps its run list
  to five lines, its charts readable and its buttons on screen at every
  window size.
- **A damaged `meta.json` no longer stops a run remembering anything**, and
  runs write their metadata atomically.
- **Help texts tell the truth.** The verification help card described a
  colour-management print path the app deliberately prevents; the gamut
  check was described as a drift check; "as measured (absolute)" read like
  a rendering intent. All corrected — and every such correction is now
  guarded by a test.

### Internal

- The test suite no longer writes to your own ChromIQ preferences.
- `docs/design/` holds the agreed, binding specifications: the measurement
  model, the message catalogue, per-target settings, the measurement windows
  and their sounds, calibration as a run type, and verification printing;
  the suite fails when code and specification disagree.
- Two purpose-built demo generators (`scripts/make_demo_projects.py`,
  `scripts/make_report_demo.py`) build test projects entirely from the real
  Argyll pipeline, and on-screen drivers verify the app against them —
  54 automated expectations for the Measurement Report alone.
