# Adding a measuring instrument to ChromIQ

Thank you for wanting to bring another instrument to ChromIQ. This guide
explains, in plain words and in the order you will need it, how an instrument
is added and why each step is there. It is written for people, and just as
much for the coding agent you may be working with.

**There are two documents, and they belong together:**

- **This guide**: the why, and the order of work.
- **[The checklist](adding_an_instrument_checklist.md)**
  (`docs/adding_an_instrument_checklist.md`): the strict companion for coding
  agents and reviewers. Numbered stages, every item checkable with a command
  or a test, what "done" means for each stage, and every place in the code an
  instrument has to be registered.

If you are a coding agent: read this guide and [`CLAUDE.md`](../CLAUDE.md) in
full, then work through the checklist stage by stage. Parts of `CLAUDE.md`
describe the maintainer's own machine and people (his folders, his display,
his session hooks, the people who approve): follow their intent, not their
paths, and read "Knut or Basti must approve" as "the ChromIQ maintainers
approve". A ready-made prompt for
your agent is in
[`docs/adding_an_instrument_agent_prompt.md`](adding_an_instrument_agent_prompt.md).

**You own an instrument but do not write code?** You can still help. Go
straight to [section 2](#2-you-own-an-instrument-chromiq-does-not-support-yet-this-is-how-you-can-help).

**Contents**

1. [Who this is for, and what we aim for](#1-who-this-is-for-and-what-we-aim-for)
2. [You own an instrument ChromIQ does not support yet? This is how you can help](#2-you-own-an-instrument-chromiq-does-not-support-yet-this-is-how-you-can-help)
3. [Talk to us first](#3-talk-to-us-first)
4. [What kind of instrument is it?](#4-what-kind-of-instrument-is-it)
5. [Finding the facts](#5-finding-the-facts)
6. [Designing the chart from what the instrument needs](#6-designing-the-chart-from-what-the-instrument-needs)
7. [Options stay open, and everything is saved](#7-options-stay-open-and-everything-is-saved)
8. [Every run type](#8-every-run-type)
9. [Behind a Beta switch, and off changes nothing](#9-behind-a-beta-switch-and-off-changes-nothing)
10. [What was saved builds as it was built](#10-what-was-saved-builds-as-it-was-built)
11. [Measuring](#11-measuring)
12. [Talking to the hardware](#12-talking-to-the-hardware)
13. [Files, text and specifications](#13-files-text-and-specifications)
14. [How we work: challenge, build, review, prove](#14-how-we-work-challenge-build-review-prove)
15. [Opening the pull request](#15-opening-the-pull-request)
16. [Common mistakes we have seen](#16-common-mistakes-we-have-seen)

---

## 1. Who this is for, and what we aim for

ChromIQ is a PyQt6 GUI for ArgyllCMS printer profiling
(`targen > printtarg > print > chartread > colprof`). Most instruments reach it
through ArgyllCMS. This guide is about the rest: an instrument ChromIQ has to
talk to itself, an instrument ArgyllCMS knows but ChromIQ does not offer yet,
or a new feature for an instrument ChromIQ already supports (charts for a
measuring table, or an instrument's indicator lights, for example).

**What we aim for.** A new instrument gets the same full support as the
others: charts made for what it physically needs, every run type, and **as
many of ChromIQ's options as possible**. People who use ChromIQ should never
find an instrument more limited than it has to be. So the defaults are the
safest values, and an option is taken away only when it has no meaning for
the instrument or the chart cannot be built with it
([section 7](#7-options-stay-open-and-everything-is-saved)).

**If you write the code, please bring:**

- **A working driver or connection**, outside ChromIQ if need be, or, for a
  device nobody has driven yet, recordings and notes that explain what its
  own program sends it ([section 5](#5-finding-the-facts)). Building a driver
  from nothing inside one ChromIQ pull request is too much for one review.
- **The instrument in your hands**, or a tester who owns one and agrees to
  try your work, for as long as the review takes.
- **Tests that use invented data only.** Nothing read from a real unit goes
  into the repository.
- **Willingness to test on the hardware** when reviewers ask something only
  the device can answer, and to report it with photos, screenshots and short
  log lines.

The maintainers cannot test hardware they do not own. That is why new support
ships behind a Beta switch ([section 9](#9-behind-a-beta-switch-and-off-changes-nothing))
and why your pull request says what was and was not tried on the device.

Nothing in this guide is a promise that a pull request will be merged, or
that a particular instrument will be supported. It is the list of things a
review will look for, written down so you can do them first.

**A few words this guide uses:**

- **Guided** and **Manual**: the two modes of the Create Chart tab. Guided
  asks a few questions and picks a sensible layout; Manual offers every
  layout option.
- **Recipe**: the full set of layout choices a chart is built from
  (`workflow/layout_engine/presets.py::LayoutRecipe`). Presets, Save as
  Defaults and the chart's own record all store recipes.
- **Target**: what the bar at the top of the window points at, that is a
  project's run, one of its verifications, or its calibration. **A target's
  own settings** are the choices ChromIQ remembers for that target in the
  project, so reopening it brings them back
  (`docs/design/per_target_settings.md`).
- **The ⓘ help**: the small round button beside an option that opens its
  explanation.
- **The instrument lease**: ChromIQ's claim on an instrument it drives
  itself, so that two windows never talk to one device at the same time
  (`core/instrument_lease.py`).
- **§M-PROPOSED**: the part of the message catalogue
  (`docs/design/unified_measurement_management.md`) where the text of every
  new window is proposed before the maintainers approve it.

Where this guide gives an example from the X-Rite i1iO table, it comes from a
chart-only Beta: ChromIQ makes charts for the table, and does not measure with
it yet.

## 2. You own an instrument ChromIQ does not support yet? This is how you can help

You do not need to program, and you do not need an AI agent. Much of what
ChromIQ has learned recently about its instruments came from owners'
recordings of what the instrument's own program says to it.

### The recording tool

The **ChromIQ X-Rite instrument probe** is a free, open-source tool:
[github.com/itsab1989/chromiq-i1io-probe](https://github.com/itsab1989/chromiq-i1io-probe).
Its README has the step-by-step instructions for each system; please follow
those, because they are kept up to date with the tool. What follows is a short
summary, checked against version 1.5.5.

- **What it does.** It looks for your instrument, writes a plain-text report
  about it and your computer, and can then guide you through a few short steps
  in the instrument's own program while it records the USB traffic between
  that program and the instrument. You can read the report before you send
  it, and by default it hides serial numbers, your user name and your home
  folder.
- **It never sends anything to the instrument.** It does not even open a
  connection to it. It changes nothing on your computer unless you say yes
  first: on a Mac, if you agree to a recording, it switches the Mac's USB
  recording interfaces on for the recording and off again afterwards; on
  Windows, if USBPcap (below) is missing, it can, after asking you, download
  USBPcap's own installer and start it, and it can offer to start itself
  again as administrator.
- **Which instruments it covers today**: X-Rite instruments only, namely the
  i1iO scanning table, the i1Pro family (original i1Pro, i1Pro 2, i1Pro 3 and
  i1Pro 3 Plus), the ColorMunki Photo / Design and the i1Studio. Instruments
  by other makers are not covered by it yet.
- **Which systems**: downloads for Windows, macOS (Intel and Apple Silicon)
  and Linux. The report works on all of them. A **recording** needs more:
  - **Windows** on a PC with an Intel or AMD processor: the free USBPcap,
    which comes with Wireshark. It installs a capture driver into Windows, and
    the tool must run as administrator to record. Windows on ARM, including a
    Windows virtual machine on an Apple Silicon Mac, cannot record.
  - **macOS**: only with System Integrity Protection (SIP) fully switched off
    for the time of the recording, and switched back on afterwards. The
    README explains how, and the risk, honestly.
  - **Linux**: `usbmon` and `tcpdump`; the makers' programs themselves do not
    run on Linux.

  The README also lists which versions of X-Rite's i1Profiler and of Windows
  still work with which instrument; please check it before you start.
- **What a recording contains.** Necessarily your instrument's **serial
  number and its factory calibration data**, because the maker's program reads
  them every time it connects. They identify your instrument, not you. So
  please share a recording deliberately. The tool keeps a copy that holds only
  the instrument's traffic, and offers to delete the full recordings, which
  can contain other USB devices such as a keyboard.
- **Nothing is uploaded.** You decide whether to send anything. To send it,
  open a [new issue](https://github.com/itsab1989/ChromIQ/issues/new) in the
  ChromIQ repository and attach it there; for the i1iO table, attach it to
  [issue #129](https://github.com/itsab1989/ChromIQ/issues/129).

### What helps even without a recording

Open an issue titled "New instrument: <make and model>" and tell us about it.
Any of these helps:

- **The chart its own program prints**: a photo or a scan of it, with a ruler
  beside it, or measurements of the patch sizes, the gaps, the margins and any
  marks.
- **Its manual**, or a link to the maker's public documentation and
  datasheet.
- **Files you made with its program**: a chart file, a measurement export, a
  settings file. Only files you made yourself; never the program itself or
  its installed files.
- **What the program asks you to do**: how the sheet is laid down or fed,
  which points you aim at, what it does when a reading fails.

Nothing here is a promise that ChromIQ will support your instrument. It helps
us understand it, and that is always the first step.

## 3. Talk to us first

Open a
[feature request](https://github.com/itsab1989/ChromIQ/issues/new?template=feature_request.yml)
titled "New instrument: <make and model>" before you write much code. Say how
it connects (USB serial, USB HID, Bluetooth, Ethernet), what your driver or
your recordings can already do, the licence, and which kind of instrument it
is (next section). Ask there too whenever your plan would contradict a design
specification in `docs/design/` or an existing message: those are binding,
and changing them is the maintainers' decision.

## 4. What kind of instrument is it?

| Kind | Route |
|---|---|
| **ArgyllCMS already drives it**, ChromIQ does not offer it yet | Registration only: lists, layout geometry, pace row. ArgyllCMS does the reading. |
| **A new feature for an instrument ChromIQ already measures with** | A change to the vendored ArgyllCMS instrument code in `native/instlib/`, recorded as a patch and in its provenance note, used only while the Beta switch is on. Every other instrument stays exactly as upstream. |
| **An instrument with its own driver that returns one reading per patch** (a spot instrument, or a strip reader whose driver hands over each patch's reading on its own) | ChromIQ's own chartread runs the session with "external values" (`-xx`, `workflow/measure_manager.py::MeasureParams.external_values`): it opens no instrument and asks ChromIQ for each patch's reading, which a small bridge fetches from your driver. chartread keeps the session, the file and all the measurement logic, so resume, re-reading and the end windows come for free. |
| **An instrument with its own driver that returns a whole strip at once** | Open an issue first: the external-values route asks for one patch at a time, so a driver that only delivers whole strips needs a design agreed with the maintainers. |
| **A measuring table or an automatic chart reader** | Open an issue first and agree the design there. Making charts for it follows [section 6](#6-designing-the-chart-from-what-the-instrument-needs); there is no general measuring route for these devices yet. |
| **A scanner or camera** | Not an instrument in this sense: ChromIQ reads a scanned chart with ArgyllCMS `scanin` (Tools > "Build profile with scanner or camera"). |

## 5. Finding the facts

Everything you build rests on facts about the instrument: its aperture, its
reading speed, the sheet it takes, the commands it understands. Collect them
before you design anything, and write down where each one came from.

**Where facts come from:**

1. **The maker's manuals and public documentation**: datasheets, user
   guides, support notes, release notes of its software.
2. **ArgyllCMS's sources and documentation**, for any instrument ArgyllCMS
   knows: they often hold decades of careful work on exactly this device.
3. **The instrument's original program, used and watched.** Run it as an
   owner would, and observe what it expects: the chart it prints (geometry,
   margins, patch sizes, gaps, marks), how the sheet is placed and aligned,
   what it asks the person to do, what it does when something fails, and the
   files it reads and writes.
4. **Recordings of the traffic** between that program and the instrument,
   made by an owner on their own device with the recording tool
   ([section 2](#2-you-own-an-instrument-chromiq-does-not-support-yet-this-is-how-you-can-help)).
5. **Your own careful measurement**: a ruler on a printed chart, a timed
   scan.

**How sure is each fact?** Keep every number about one instrument in one
module, each with its value, its source and one of four levels, and have the
layout code read its numbers from there and nowhere else; then the next
recording or datasheet corrects a number without anyone touching layout
logic. `workflow/i1io/table_facts.py` is such a module, and its four levels
are the ones to use:

- **`VERIFIED`**: shown by a source anyone can check (the maker's own pages
  or files), or arithmetic that holds on every case recorded;
- **`PUBLISHED`**: a published figure nobody on the project has checked on a
  real device yet;
- **`LIKELY`**: one reading fits all the evidence, but it is not proved;
- **`OURS`**: a design choice of the project's own, with its reason.

**A guess is a comment, never a value.** Something you only suspect is
written down as a note beside the code or in the issue, so the next recording
can confirm or drop it. It never becomes a number the code uses, and never a
command, a movement or a timing that a device is driven with
([section 12](#12-talking-to-the-hardware)).

**Keep it lawful and plain.** Observing how a program behaves, and recording
the traffic of your own device, to make another program work with it, is
what this project does. It never copies the maker's program code, firmware,
calibration data, stored instrument memory, chart files or tables into the
repository. Facts are written down in our own words, with a note of where
they came from. Recordings stay outside the repository and its tests. An
owner who attaches one to a GitHub issue makes it public, so it is shared
deliberately, by its owner's choice
([section 2](#2-you-own-an-instrument-chromiq-does-not-support-yet-this-is-how-you-can-help)).

*In [the checklist](adding_an_instrument_checklist.md): stage 0.*

## 6. Designing the chart from what the instrument needs

ChromIQ has its own layout engine (`workflow/layout_engine/`). It places every
patch, spacer, label, mark and line of text itself, and writes the chart
files ArgyllCMS reads. So the question is never "which of ArgyllCMS's
`printtarg` layouts fits this instrument?". It is: **what does this
instrument need from a sheet, and what is the best chart we can design for
that?** `printtarg` is a reference only for the fields ArgyllCMS expects in
its files.

**Start from the physical facts:**

- **the aperture**, and how far the instrument may sit off a patch centre;
- **the reading direction**: along a strip, a whole row, or patch by patch;
- **run-in and run-out**: the blank paper it needs before the first and after
  the last patch, to reach speed, to stop, or to see a clean edge;
- **readings per patch**, for a scanning instrument: how often it reads and
  how fast it moves, which sets the shortest usable patch;
- **guides and aiming**: a ruler, a track, an arm, printed marks it is aimed
  at, a camera that searches for marks, and where nothing may be printed;
- **the sheet**: the sizes it takes, the area it can reach, how the sheet is
  laid down or fed, and which edge goes first;
- **the person**: where they stand and which way they read the sheet. Ask an
  owner rather than guessing.

**Then design freely.** Use the engine's ordinary vocabulary wherever it fits
(strips, patch numbers, spacers, gaps): then most layout options work for the
new instrument without new engine code. Work out the capacity from the
geometry, so Guided's patch count always matches what is printed. Every mark
and every line of text serves a purpose you can name, stays out of what the
instrument reads, and is checked before any file is written. Anything that
costs patches can be an option. If the sheet lies turned on the instrument,
show it turned on screen, never by turning the files. Print the chart's name
and page number on every sheet, so sheets can be told apart.

*In [the checklist](adding_an_instrument_checklist.md): stages 0 and 2.*

## 7. Options stay open, and everything is saved

This is the part that decides how useful the instrument will be.

**The rule:**

- **The defaults are the safest values**: what gives a good reading on a
  first try for a person who changes nothing.
- **An option is unavailable only when it has no meaning for the instrument,
  or when the chart cannot be built with it.** It is never taken away merely
  because a careless value could spoil a reading. ChromIQ trusts people with
  such options on every other instrument (margins, gaps, label offsets), and a
  new instrument should not be more locked down than the rest.
- **Behave as the other instruments do** with the same option: allow it, and
  warn where they warn. For example, a margin smaller than the instrument's
  minimum in Preferences is not refused: the chart is made, and Create
  Chart's "Measured from Preview" panel flags that edge
  (`workflow/margin_inspector.py::check_violations`).
- **A limit is fine where the chart would otherwise not exist** (margins that
  keep the marks clear, a sheet the instrument cannot reach). Say the limit in
  the control's help.
- **An unavailable control explains itself**: its tooltip starts with its own
  reason, and it shows the value the instrument really uses, not what the
  previous instrument left in it.

**Map every existing option, one by one.** List every option of Create Chart
(Guided, Manual and its expert options, Pages, Custom paper), of Preferences
(Chart Layout, instrument limits, Printing) and of the Measure tab. For each,
write down whether it works, works with limits (which, and why), or is
unavailable (and why, by the rule above). Reuse an existing control with the
new instrument's meaning; never add a second one beside it.

**Everything that works is saved everywhere.** Every option the instrument
supports survives all four places a setting can live:

1. **Save as Defaults**, in Guided and in Manual, across a restart;
2. **presets**, the user's own and any built-in ones;
3. **a target's own settings**, which are loaded and written as
   `docs/design/per_target_settings.md` says;
4. **the chart's own record**, so a reopened project and "Restore Used Chart"
   show exactly what was built.

One table-driven test walks every recipe field through all four, so a field
that someone adds later without saving it makes the suite fail. Fields that
only one instrument uses are written only for that instrument, so every other
recipe stays byte for byte as it was.

**An instrument default is not an override.** When a person chooses the
instrument, every field gets the instrument's stored or default value; but a
value the person has chosen, by hand or with a preset, is never overwritten
(`docs/design/per_target_settings.md` §4c).

*In [the checklist](adding_an_instrument_checklist.md): stage 3.*

## 8. Every run type

ChromIQ has three run types, chosen in the target bar: **Profiling**,
**Verification** and **Calibration** (Calibration is offered while
"Enable calibration options" is ticked in Preferences;
`core/measurement_target.py::RUN_TYPES`). A new instrument supports **every
run type, in Guided and in Manual**: Create Chart makes Verification and
Calibration charts for it with the same options and flow as for any other
instrument, and its files land where those run types keep theirs
(`docs/dev_folder_layout.md`).

Where something cannot work yet, the app says so visibly, in a friendly
window that explains what is not available and what the person can do
instead, never by leaving the instrument out of a list in silence. For
example, the i1iO table's Beta makes Verification and Calibration charts for
the table, and pressing Start on such a chart explains that measuring with
the table is not available yet and offers the instrument by hand
(`tests/test_i1io_run_types.py`). Read `docs/design/calibration_run_type.md`
and the Verification parts of `docs/design/per_target_settings.md` first.

*In [the checklist](adding_an_instrument_checklist.md): stage 4.*

## 9. Behind a Beta switch, and off changes nothing

New hardware support the project cannot test itself goes behind a checkbox in
**Preferences > Beta**, off by default.

- **With it off, ChromIQ is the previous release**, for every user, in every
  list, window and file. **With it on, every other instrument is unchanged.**
  This is what lets the maintainers ship something they cannot test.
- **Honest about the risk.** The switch's ⓘ says what it adds, the limits of
  this version, how the work was done (for example "worked out from one
  owner's recording, not from the maker's documentation"), whether anybody has
  tried it on real hardware, what a tester can check, and how to report it.
  Switching it on opens a consent window that says plainly that the person
  uses it at their own risk; "Keep it off" is the default button.
- **Restart to apply** when the switch changes what the window offers (the
  lists are built once); a switch that only changes what happens during a
  measurement can be read at every Start.
- **Stale settings are harmless.** Someone may turn the switch on, make a
  chart, and turn it off again. Their saved values for the instrument are kept
  untouched for the day it is on again, a chart made for it is refused kindly
  at Start with a window that names the option, and an untouched project's
  files stay byte for byte as they were.

**Proof, in two parts.** Tests, four nets of them (the checklist names them),
check what somebody thought of. A **file comparison** checks everything else:
the same charts, built by the previous release and by your branch, must come
out byte for byte the same. ChromIQ has no ready-made script for this yet, so
you write a short one and put it in your pull request. The method:

1. Check out the previous release in a second worktree, beside your branch:
   `git worktree add ../chromiq-previous v4.3.33` (use the latest release
   tag, `git tag --sort=-v:refname`).
2. Write one script that builds a fixed list of charts: every instrument on
   offer, the common papers, and a handful of option combinations, each from
   a recipe (`LayoutRecipe(...).build_kwargs()` passed to
   `workflow/layout_engine/chart.py::build_chart`, with the same `.ti1` for
   every build). Pass a fixed `seed=` so the patch order is the same in both
   trees (in the app, this is "Use a fixed seed (reproducible)" in Manual's
   options), and a fixed `chart_date=` so any date printed on the sheet is
   the same. Add recipes, presets and a project saved by the previous
   release.
3. Run the same script in both trees (switch off; then switch on, for the
   other instruments) and compare every output file byte for byte.
4. Normalise only what really differs per build, and say what you
   normalised: the `CREATED` line of the `.ti2` (and of a `.ti1` made by
   targen) holds the time of the build, so compare those files with that one
   line taken out. Keep the layout summary stamp switched off in the
   comparison, because it prints the version, rather than normalising pixels.

*In [the checklist](adding_an_instrument_checklist.md): stages 1 and 10.*

## 10. What was saved builds as it was built

People keep presets for years and reopen old projects. When you change how a
chart is laid out, **a recipe, project or preset saved by an older version
must still build exactly as that version built it.**

- **Mark what the new version saves, and treat only an unmarked file read
  from disk as old.** Every path that works in memory (a recipe handed from
  Guided to Manual, the settings Guided builds with, Save as Defaults after
  loading an old preset, a new project seeded from the current one) is new,
  even if a field is missing on the way.
- **A default you may change later is stored once chosen**, so someone who
  chose today's default keeps it when the default changes, while "not stored"
  keeps meaning "never chosen".
- **The panel, the record and the print are one state.** What the panel
  shows, what is recorded with the chart and what is printed are always the
  same. If a value is raised to a minimum for the build, the panel shows the
  raised value and the record holds it.
- **Check a chart against the recipe it was built with**, never against what
  the panel holds now.
- **A chart records what it was made with**, and a chart without the record
  reads as "unknown", never as a guess.

*In [the checklist](adding_an_instrument_checklist.md): stage 5.*

## 11. Measuring

- **The same Start preflight as every instrument**, in the same order, before
  any device work: recovery of an interrupted session, the new-run and chart
  guards, the instrument lease, the checks for a mismatched measurement and
  for verification, and the questions before a measurement is replaced. A
  route through chartread gets them by itself; a start of your own runs every
  one, and a test proves it.
- **Endings, resume and partial results** reuse the existing windows and the
  rules of `docs/design/measurement_exit_strategy.md`. A replaced measurement
  is archived, never destroyed. A partial result belongs to its own chart
  only. Resume is bound to the device's identity, not to an address that can
  change.
- **The Qt rules that keep the process alive**: no device work on the GUI
  thread; worker threads that are not parented to a widget and are held until
  they finish; signals connected to named methods, never to a lambda that
  captures `self`; automatic garbage collection never switched on. Stop is
  cooperative and says what state the device is left in.
- **If a crash could leave the device changed, say so next time**: record it
  while it is true, and ask at the next Start (for example, to unplug and
  replug the instrument).
- **Errors reach the person as friendly windows**, never as raw exception
  text, and log lines are written for a person and translated too.

*In [the checklist](adding_an_instrument_checklist.md): stages 6 and 7.*

## 12. Talking to the hardware

These rules hold for everything that sends anything to a device. They do not
loosen with the open-options rule of [section 7](#7-options-stay-open-and-everything-is-saved):
a person may choose any chart layout, but ChromIQ never sends a device a
command it does not understand.

- **Only commands that are understood**, from documentation or from
  recordings of the maker's own program, and only in the situations they were
  seen in.
- **Each model and generation is its own device.** Two generations of one
  instrument family can use different requests, byte formats and endpoints.
  Never assume a model speaks the language of another without a recording of
  it, and refuse an unknown model, firmware or sensor version before anything
  is sent or moves, naming what was found.
- **Never copy something that could change a reading.** If the maker's
  program does something that could reach the sensor (lights on while
  measuring, say), keep it as it would be without the feature.
- **Never write to the instrument's memory**, settings, calibration or
  firmware.
- **Never move, lower or lift mechanics on a guess.** Movement needs commands
  whose meaning is known, limits taken from the recordings, a timeout on
  every move and a check that it arrived. Until a command is understood, it
  is not sent, and the feature waits.
- **No command "just to look"**, fixed serialisers only, every wait with a
  timeout, every reply checked before use, and every command the code can
  send listed with what it does.
- **A simulator first.** Before anything runs on a real device, build a fake
  device from the recordings, with its timing and its faults (no reply, a bad
  reply, a move that falls short, a pulled cable), and test against it. Its
  data is invented, shaped like the recordings.
- **Testers who know what they agree to**: the consent window and ⓘ above, a
  short list of what to check and how to report it, and small steps (read
  only first, then the smallest safe action), each ending with the tester's
  report.
- **Licence and provenance.** ChromIQ is GPL-3.0; vendored code must be
  compatible, and a maker's SDK or binary library cannot be bundled. A
  provenance note says how the protocol was learned and that nothing of the
  maker's was copied.

*In [the checklist](adding_an_instrument_checklist.md): stage 8.*

## 13. Files, text and specifications

These are the project's usual rules; the checklist has the details and the
tests.

- **Paths** go through `Project` / `Run` / `Calibration`
  (`core/file_manager.py`, `docs/dev_folder_layout.md`). **Settings** live in
  `AppSettings` (`core/settings.py`). **No device data** in the repository or
  a pull request.
- **Names**: the short model name in every list, the full name with the
  vendor in the files. Where one entry stands for a family, the files carry
  the family name and record the generation separately, so a later generation
  never renames a file already written.
- **Text**: friendly, complete, easy to understand and correct; every string
  in `tr()`; all 13 languages, with a second, independent translation pass;
  no em dash in new English text.
- **Messages**: every new window gets an ID in §M-PROPOSED of
  `docs/design/unified_measurement_management.md` first, word for word the
  same as in the code. Proposed texts are shown in the app; the maintainers
  approve them afterwards.
- **Specifications in `docs/design/` are binding.** Read the ones you touch
  before you change code. A conflict is raised with the maintainers, not
  fixed in passing. New behaviour is written as "Awaiting confirmation"; only
  a maintainer's confirmation makes it confirmed.

*In [the checklist](adding_an_instrument_checklist.md): stage 9.*

## 14. How we work: challenge, build, review, prove

1. **Challenge before you build.** Write the plan (the facts, the chart, the
   options table, the run types, the hooks, the tests) and have someone else
   challenge it: a maintainer in the issue, or a separate agent session that
   did not write the plan.
2. **Build** with tests, in small commits.
3. **Independent review after building**, by someone who did not build it
   and is given the diff rather than your conclusions, with the switch on and
   off. Fix what they find, and review again until nothing that matters is
   left.
4. **Prove it in the real app, in a real window**, with sandboxed settings and
   a scratch output folder, the switch on and off. Never print to a real
   printer from a script, and never take the keyboard from a person who is
   typing.
5. **One green gate** of the full suite on the final tree, inside the
   project's `.venv` (set up as `CLAUDE.md` describes, with ArgyllCMS 3.5.0):

   ```bash
   QT_QPA_PLATFORM=offscreen pytest --runslow -n auto -q > /tmp/chromiq-gate.txt 2>&1
   echo "exit=$?"
   ```

   It is green when the count line says `N passed` with no `failed` and the
   exit code, read from pytest itself and not through a pipe, is 0. Do not
   edit files while it runs. The checklist's stage 10 has the quicker checks
   to run first, and the Windows command.

*In [the checklist](adding_an_instrument_checklist.md): stage 10.*

## 15. Opening the pull request

One topic per pull request, based on the current `master`. The description
says what the instrument is and which route it uses; the facts the chart was
designed from, with their sources and confidence; the options table; which run
types work and what the app says about the rest; the tests and the file
comparison that prove "off changes nothing"; **what was tried on the device and
what was not**; the commands the driver sends and its licence and provenance;
the new message IDs and specification blocks; the translations you are unsure
of; who challenged and who reviewed, and what they found; the gate's count
line and exit code; and screenshots from the real app, switch on and off.
Attach the checklist with every item marked done, not applicable (why) or
open.

## 16. Common mistakes we have seen

These come from review rounds of instrument work on this project. They are
nobody's fault: most are invisible until somebody knows to look.

| Mistake | Do this instead |
|---|---|
| Designing the chart from a `printtarg` layout | Start from the physical facts and design with ChromIQ's own engine. |
| Options taken away because a careless value could spoil a reading | Safe defaults, options open, warnings where the other instruments warn. |
| An option that works in the panel but is lost after Save as Defaults, in a preset or in a reopened target | One table-driven test over every field and all four places. |
| A run type left out in silence | Every run type in Guided and Manual, or a window that says what is not available yet. |
| Changes that reach everyone | Everything behind the Beta switch, proven by tests and a file comparison. |
| Recipes handed over in memory treated as old ones, so the panel showed one style and the chart was built with another | Decide "old" only where an unmarked file comes off the disk. |
| A chart checked against the panel's current recipe, giving a false warning | Check it against the recipe it was built with. |
| The chart's name and page number dropped at an extreme text size | Test the extremes; the chart's identity prints on every page. |
| One generation's commands reused for another | A recording per generation; refuse unknown models before anything is sent. |
| Behaviour copied from the maker's program that could change a reading | Keep everything that could reach the sensor as it was. |
| Values inherited from the previously chosen instrument (touching patches from 0 mm gaps) | Load the instrument's own stored or default values when it is chosen. |
| Duplicated controls beside the shared ones | Map every existing option and reuse the control. |
| Text turned for a stance nobody had | Ask an owner how the sheet is held and fed. |
| A long note about one instrument inside a shared settings section | Controls explain themselves in their tooltip; the instrument is described in its ⓘ. |
| Raw errors and English-only log lines | Friendly windows from the catalogue, `tr()` everywhere. |
| Tests that need the author's device or recordings | Invented data only; every test runs anywhere. |
| An unrelated change riding along | One topic per pull request. |

The checklist's last stage lists every mistake with the test or check that
catches it.
