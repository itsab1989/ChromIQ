# Recording plan for the X-Rite i1iO 3 table

**For owners of an X-Rite i1iO 3 scanning table (the third generation, made for
the i1Pro 3 or the i1Pro 3 Plus) who would like to help ChromIQ learn to drive
it.**

Thank you for reading this. This page is a complete plan for one recording
session with your own table, X-Rite's own software (i1Profiler) and our free,
read-only recording tool. It is written so that you can follow it alone, with
the table beside you, without knowing anything about programming or USB.

It is long because it is complete, not because it is hard. Every block is a
short list of single actions in i1Profiler, the way you use it anyway. The
plan is ordered so that **the most useful blocks come first**: if you stop
after Part 1, we already have the core.

This plan is the worked example of
[section 2a of the guide for adding an instrument](adding_an_instrument.md#2a-recording-an-instrument-that-moves).

**Contents**

1. [In short](#1-in-short)
2. [What this is, and what we will do with it](#2-what-this-is-and-what-we-will-do-with-it)
3. [What is recorded, and what is not](#3-what-is-recorded-and-what-is-not)
4. [Safety: everything here is normal use](#4-safety-everything-here-is-normal-use)
5. [What you need](#5-what-you-need)
6. [The sheets to print](#6-the-sheets-to-print)
7. [How to record, step by step](#7-how-to-record-step-by-step)
8. [Part 1: the core (ESSENTIAL)](#8-part-1-the-core)
9. [Part 2: every state the table can be left in (ESSENTIAL)](#9-part-2-every-state-the-table-can-be-left-in)
10. [Part 3: the whole bed, the vendor's speed, the conditions (IMPORTANT)](#10-part-3-the-whole-bed-the-vendors-speed-the-conditions)
11. [Part 4: extras (NICE TO HAVE)](#11-part-4-extras)
12. [After the blocks: photos, files, a few questions](#12-after-the-blocks-photos-files-a-few-questions)
13. [What to send, and how](#13-what-to-send-and-how)
14. [What a recording cannot tell us, and what happens next](#14-what-a-recording-cannot-tell-us-and-what-happens-next)
15. [The one-page checklist](#15-the-one-page-checklist)
- [Appendix A: why each block is there](#appendix-a-why-each-block-is-there)
- [Appendix B: what we assume about the i1iO 3](#appendix-b-what-we-assume-about-the-i1io-3)

---

## 1. In short

- **What:** you use your i1iO 3 in i1Profiler as you normally would, plus a
  few things you would normally avoid (cancelling, quitting at an odd moment,
  switching off), while our recording tool listens to the USB cable.
- **Why:** ChromIQ only ever sends a device commands it has seen X-Rite's own
  software send to that very model. Your recordings are where those commands
  come from.
- **How long:** about **5 to 6 hours in all**, split into four parts. You can
  do them on one day or on several, and stop after any block.

  | part | what it gives us | priority | time |
  |---|---|---|---|
  | Part 1, blocks B01 to B07 | how the table is recognised, started, calibrated, aimed, read in rows and patch by patch, ended and quit | ESSENTIAL | about 75 min |
  | Part 2, blocks B08 to B14 | every state a previous session can leave the table in, and how X-Rite's software gets it back | ESSENTIAL | about 60 min |
  | Part 3, blocks B15 to B24 | the whole bed, every speed and patch size, retries, several pages, the measurement conditions, the limits, errors | IMPORTANT | about 2.5 to 3 hours |
  | Part 4, blocks B25 to B28 | idle behaviour, the instrument by hand, a ChromIQ chart in i1Profiler | NICE TO HAVE | about 40 min |

- **Nothing is sent anywhere by itself.** You decide what to send, after
  you have looked at it.
- **Nothing here is a promise** that ChromIQ will be able to drive an i1iO 3.
  It is the first step, and with the first table we supported it was the
  step that decided everything else.

## 2. What this is, and what we will do with it

ChromIQ drives the previous model, the i1iO 2 with an i1Pro 2, itself: it
moves the arm, aims, calibrates and reads a chart in rows or patch by patch,
without i1Profiler. That was learned entirely from recordings like the ones
this plan asks for, made by the owner of that table over several rounds.

We learned one thing above all from that work: **every time a recording was
missing, we had to guess, the guess was too careful, and fixing it cost
another round with the owner.** Examples, all from the first table:

- We had recordings of the arm going home only from a few places. So the
  first versions refused to bring the arm home from anywhere else, although
  X-Rite's software does it from everywhere. Fixing that took two releases.
- Nobody had recorded what happens when i1Profiler is closed while the table
  is still in its aiming mode. When ChromIQ left the table in that state, the
  next start refused it, and only i1Profiler could get the table out. The
  recordings that showed the way out came a week later.
- From one corner of the bed, X-Rite's software goes home by a detour. We
  found that out only from a recording made after the first real runs.
- We had the speeds of a few rows only, so ChromIQ first read rows more slowly
  than i1Profiler does.

So this plan asks for **everything at once**: every way of starting, every
way of ending, the whole bed, every speed. Then the first ChromIQ version for
your table can do what i1Profiler does, at i1Profiler's speed, from the start.

**What we do with the recordings:**

1. Read every command i1Profiler sent and every answer the table gave, with
   the time of each, and match them to your notes.
2. Write down, in our own words, what each command does, how long each move
   takes, and which states the table reports.
3. Build a simulated table from that, and test ChromIQ's code against it
   (thousands of runs, with every kind of fault), long before anything is
   sent to a real table.
4. Only then, and only if the recordings show that it can work, offer you a
   first ChromIQ version for your table, step by step, with your agreement
   before every step (section 14).

ChromIQ can already make charts for the i1iO tables and bring back the
measurement i1Profiler made of such a chart (Preferences > Beta, "X-Rite i1iO
support"). That keeps working whatever comes of this plan.

## 3. What is recorded, and what is not

**The recording tool** is the "ChromIQ X-Rite instrument probe", free and
open source:
[github.com/itsab1989/chromiq-i1io-probe](https://github.com/itsab1989/chromiq-i1io-probe).
Its README is the full manual; section 2 of
[the guide](adding_an_instrument.md#2-you-own-an-instrument-chromiq-does-not-support-yet-this-is-how-you-can-help)
summarises it. In short:

- **It never sends anything to the table or the instrument**, not one byte,
  and it never opens a connection to them. It only listens.
- **On a Mac** it records with the system's own `tcpdump`, which works only
  while System Integrity Protection (SIP) is fully switched off. The README
  says honestly what that means and how to switch SIP on again afterwards.
  The tool then keeps a copy that holds only the X-Rite devices' traffic, and
  puts it into one `SEND-THIS-<date>.zip`.
- **On Windows** (a PC with an Intel or AMD processor) the table session of
  version 1.6.6 does not record by itself: you record with Wireshark and its
  USBPcap part while the tool times your steps (section 7 says how). Windows on
  ARM, and a Windows virtual machine on an Apple Silicon Mac, cannot record.
- **Its report hides** your user name and home folder, replaces serial
  numbers by codes, and names other USB devices only by their numbers.

**What a recording necessarily contains, said honestly:**

- the serial numbers of the table and the instrument, and the instrument's
  factory calibration data, because i1Profiler reads them every time it
  connects. They identify your devices, not you;
- the colour values the instrument measured from your sheets;
- possibly a little traffic of another USB device that shares the
  instrument's connection. So please **unplug every other USB device you can**
  while you record (disks, memory sticks, printers, phones, card readers); a
  keyboard and a mouse may stay.

**What we never do with it:** we never put a recording, a serial number,
calibration data or anything read from your devices into ChromIQ's code or
tests. Only conclusions in our own words (a speed, a command form, a time)
go into the project, with a note of where they came from. We never take
X-Rite's software apart; we only look at what it says over the cable.

## 4. Safety: everything here is normal use

**Everything in this plan is done in X-Rite's own software, on your own
table, in ways the software allows.** The recording tool cannot move
anything. The few blocks that do something unusual (switching the table off
during a measurement, pulling the USB cable) are things that happen in real
life anyway; each is marked **optional**, and you can skip it without a
second thought.

Before you start, please read these four lines once:

1. **The power switch of the table is the emergency stop.** Switch it off,
   and the arm stops at once. Know where it is before Part 1.
2. **Keep your hands away from the arm while it moves.** Only touch the arm
   when i1Profiler asks you to aim, or when this plan asks you to move it
   while the table is idle.
3. **Never force the arm.** If this plan asks you to move the arm by hand and
   it does not move easily, stop, do not push, and skip that part.
4. **Only your sheet on the bed.** No rulers, tape or tools on the table while
   it measures.

One more honest note: i1Profiler itself writes a small record into an
i1Pro 3 during normal use (an earlier recording of an i1Pro 3 showed it). That
is X-Rite's own behaviour and happens whenever you use i1Profiler. ChromIQ
never copies such a write.

## 5. What you need

- [ ] **The i1iO 3 table**, with its power cable and its USB cable.
- [ ] **The instrument** on it: an i1Pro 3 or an i1Pro 3 Plus. If you have the
      polarisation filter for it, keep it at hand (block B21).
- [ ] **i1Profiler**, the version you normally use, already able to see the
      table. Please **write down its version** (in i1Profiler's Help or About
      window) and **do not let it update itself** during the plan.
- [ ] **The recording tool, version 1.6.6 or newer**, from its
      [latest release](https://github.com/itsab1989/chromiq-i1io-probe/releases/latest).
      One file for your system (Windows, macOS, Linux).
- [ ] **On Windows:** Wireshark with its USBPcap part (from wireshark.org;
      tick "USBPcap" in its installer, then restart Windows).
      **On a Mac:** be ready to switch SIP off for the recording and on again
      afterwards (the tool's README).
- [ ] **The sheets of section 6**, printed in i1Profiler.
- [ ] **A ruler** in millimetres, and **a phone camera** for a few photos.
- [ ] **A plain text file `notes.txt`** in a new folder, for example
      `i1iO3-recordings` on your desktop, where you write one line per block
      (section 7).
- [ ] **Time**: about 75 minutes for Part 1. The rest can follow later.

## 6. The sheets to print

Please make every chart in **i1Profiler's own test chart step** for the
i1iO 3 (in the printer profiling workflow), with your instrument chosen. That
way i1Profiler measures charts it made itself, which is the normal use we want
to record. Colour does not matter much for most blocks; any printer and any
plain paper that the table holds flat is fine, unless a block says otherwise.

**Please save each chart in i1Profiler** (it offers its own chart file, for
example a `.pxf` or `.txf` file, or the whole workflow, a `.pwxf` file), and
write its file name and settings into `notes.txt`.

| name | what to make in i1Profiler | copies | used in |
|---|---|---|---|
| **Sheet S** (small) | 3 rows of about 10 to 12 patches, at the **smallest patch size** i1Profiler offers for scanning on the i1iO 3, on an ordinary A4 or Letter page. | 2. Cut one copy down to the printed area plus about 2 cm on every side: **Sheet S-cut**. | Parts 1, 2, 3 |
| **Sheet F** (full page) | As many patches as fit one page at the **smallest patch size**, on the **largest page size** i1Profiler offers for the i1iO 3 (write down which it is). | 2. Keep one clean, flat and out of the light: it is the **reference sheet** of block B24. | B16, B17, B24 |
| **Sheet L** (large patches) | One page at the **largest patch size** i1Profiler offers. | 1 | B17 |
| **Sheet P** (two pages) | A chart with more patches than fit one page, so that i1Profiler lays it out on **two pages**. | 1 of each page | B19 |
| **Plain sheets** | Plain paper, unprinted: three A4 or Letter sheets, and one sheet **larger than the bed** (A3 or Tabloid) if you have one. | | B15, B18, B23 |

If i1Profiler offers more than one patch size for scanning, please note the
whole list it offers, and the smallest and largest it allows for patch by
patch reading too. If it offers a "Measure Chart" function for the table (for
measuring a sheet it did not make), note that too.

## 7. How to record, step by step

The plan is split into **recording runs**. One run = one start of the
recording tool, from its start to its end. Parts 1 and 2 are one run each;
Part 3 can be one or two; Part 4 one.

### The recipe for one run

1. **Unplug every other USB device you can** (section 3).
2. **Switch the table on and plug it in.** Start i1Profiler only when a block
   says so.
3. **Start the recording tool.** On Windows: right-click it, "Run as
   administrator". On a Mac: as its README says, with SIP switched off.
4. It looks for your instruments, then asks what you would like to do.
   Choose **1. record an i1iO table**.
5. It asks three short questions: answer **i1iO 3**, your instrument
   (**i1Pro 3** or **i1Pro 3 Plus**), and your i1Profiler version.
6. **On Windows**, look for the line "USB recorder attached". Only "yes" means
   the recording can see your table. If it says "no", follow what it says
   (usually: unplug the table, restart Windows with "Restart", plug it in
   again). Then start **Wireshark**, select **all** USBPcap entries (hold Ctrl
   and click each one) and start recording, before you go on. When the tool
   asks "Is the recording running? Shall I start the walkthrough?", answer
   yes. On a Mac the tool starts the recording itself, after asking for your
   password.
7. The tool shows **its own five steps**. They were written for the i1iO 2.
   For this plan we use only its **step 1, as a container for the whole run**:
   - at "STEP 1 of 5", press **Enter** to start it (ignore its text);
   - now do the blocks of this run, in order (below);
   - when the last block of this run is done, type **`e`** and press Enter;
   - it asks one line about the arm: type "see notes" or press Enter;
   - press **Enter** to go on, then type **`s`** and Enter at each of the
     steps 2 to 5 to skip them;
   - it asks a few questions about the chart and the settings: answer what
     fits, or press Enter to skip.
8. **At the end:** on a Mac the tool switches its recording interfaces off,
   makes the X-Rite-only copy and writes one `SEND-THIS-<date>.zip`; it offers
   to delete the full recordings. On Windows, stop Wireshark and save the
   recording (File > Save As) into your `i1iO3-recordings` folder, named after
   the run, for example `run1-part1.pcapng`, and keep the tool's report beside
   it.
9. On a Mac, after the last run: **switch SIP back on**, as the tool's last
   box says.

### Inside a run: one block

Everything you type into the tool's window during step 1 is kept **with the
exact time**, which is how we find each block in the recording. So, for
every block:

1. Click into the tool's window.
2. Type the block's **label** and the word `start`, for example
   `IO3-B04 start`, and press Enter.
3. Do the block's steps in i1Profiler.
4. Whenever you see something worth noting (the arm starts, stops, goes
   home, the instrument's light changes, i1Profiler shows a message), click
   into the tool's window, type a few words and press Enter. Four single
   letters have a fixed meaning: `a` = the arm starts moving, `l` = the
   instrument's light comes on, `d` = the head goes down, `u` = the head goes
   up.
5. Type the label and `end`, for example `IO3-B04 end`, and press Enter.
6. Write **one line in `notes.txt`**: the label, the time on your clock, and
   what you saw the arm do. For example:
   `IO3-B04 14:32 arm went along each row once, left to right, then straight home; i1Profiler said "Measurement complete"`.

**Two things to avoid in the tool's window:** never type only `e`, `end` or
`done` on a line until the run is finished (that ends the step), and do not
press Ctrl-C (it ends the run; what was recorded until then is kept).

**After a click in i1Profiler**, click into the tool's window again before you
type, so that your keys land in the tool and not in i1Profiler.

**Measurements: save each one.** Whenever a block measures something, save
the measurement in i1Profiler **in two forms**, named after the label (for
example `IO3-B04`): i1Profiler's own measurement file, and an export as a
**CGATS text file (`.txt`) with the spectral data** if i1Profiler offers it.
A recording paired with i1Profiler's own result of the same measurement tells
us far more than either alone, and a measurement from another session cannot
be paired later.

**If something goes wrong in a block** (i1Profiler shows an error you did not
expect, the arm does something odd): that is a result, not a failure. Note
it, let the table come to rest, and go on with the next block. If the table
seems stuck, switch it off with its power switch, note that, and go on.

**A note about switching off and pulling the cable.** A few blocks switch the
table off and on (B03, B12, B13) or pull its cable (B14), so the table
connects afresh in the middle of a run. On a Mac the tool keeps the table's
traffic by its USB ID in every packet, so that should be fine. On Windows we
have not checked yet whether a cleaned copy (section 13) still holds the table
after it came back. So please **keep the full recordings on your computer**
until we have looked at what you sent (do not send them publicly: they can
hold other devices' traffic). On a Mac, answer the tool's offer to delete them
with no for now; we will tell you when they can go.

---

## 8. Part 1: the core

**ESSENTIAL. One run, about 75 minutes. Sheets: S.** If you do only this
part, we can already tell whether the i1iO 3 speaks the same language as the
i1iO 2, and what its normal measurement looks like from start to end.

### B01. The report and a look at the table (about 5 min)

**Label:** `IO3-B01`. **This tells us** which USB devices the table and the
instrument are, which decides almost everything else.

1. With the table switched on and plugged in, and i1Profiler **not** running,
   start the recording run (section 7, steps 1 to 7).
2. Type `IO3-B01 start`.
3. Wait 30 seconds and touch nothing.
4. Type `IO3-B01 end`.
5. In `notes.txt`: where the arm stands now (its resting place), whether the
   instrument is in the arm, and whether the table shows any light.

### B02. Start and quit i1Profiler, table already on (about 5 min)

**Label:** `IO3-B02`. **This tells us** how i1Profiler finds the table and
the instrument, the first commands and answers, and how it lets go of them
when it quits.

1. Type `IO3-B02 start`.
2. Start i1Profiler.
3. Wait until it shows that it has found the table and the instrument.
4. Wait 20 seconds more. Touch nothing.
5. Quit i1Profiler normally (its menu, Quit or Exit).
6. Wait until it has closed, and 10 seconds more.
7. Type `IO3-B02 end`.
8. Note: did the arm move? Did the instrument's light change?

### B03. Cold start: the table switched on while recording (about 5 min)

**Label:** `IO3-B03`. **This tells us** what a just-switched-on table reports
and the start-up i1Profiler then sends (on the i1iO 2 a just-switched-on
table needed its own start-up, different from a warm one).

1. Type `IO3-B03 start`.
2. Switch the table **off** at its power switch. Wait 10 seconds.
3. Switch it **on** again. Wait until it is quiet (note what it does by
   itself: does the arm move?).
4. Start i1Profiler. Wait until it has found the table.
5. Note what the arm does.
6. Quit i1Profiler. Wait 10 seconds.
7. Type `IO3-B03 end`.

### B04. Calibration on the table (about 5 min)

**Label:** `IO3-B04`. **This tells us** where the instrument is calibrated,
how the arm gets there and back, and what i1Profiler asks of you.

1. Type `IO3-B04 start`.
2. Start i1Profiler and choose a measurement on the table with Sheet S, up to
   the point where it calibrates (the calibration is usually the first thing
   it does when you start a measurement).
3. Let it calibrate, exactly as it asks. Note **where** it calibrates (on a
   white tile on the table, in the instrument's own holder, elsewhere) and
   what it asks you to do.
4. If it then goes on to aiming, stop here: **Cancel** in i1Profiler and let
   the arm come to rest.
5. Type `IO3-B04 end`.

### B05. Sheet S read in rows, to its normal end (about 15 min)

**Label:** `IO3-B05`. **This tells us** the whole normal measurement: the
aiming, the moves, the scan of each row with its speed, how reading and
movement are timed against each other, the way home and the end of the job.

1. Lay Sheet S in the **middle** of the bed, as i1Profiler shows, and switch
   the sheet hold on if your table has one (note whether it has one, and
   whether you use it).
2. In i1Profiler, set up the measurement of Sheet S in **scanning mode** (rows
   read as strips; i1Profiler may call it scan or strip mode; note the exact
   name), with its **default speed** and **M0** (or the default condition).
3. Type `IO3-B05 start`.
4. Start the measurement. Let it calibrate if it asks.
5. **Aim** at the points it asks for, exactly as it asks. Note how many points,
   which ones, and whether you confirm each with the **instrument's button** or
   with a click on the screen (please use the button if it allows both, and
   note that).
6. Let it read the whole sheet. Please **do not cancel**. Type `a` when the arm
   starts along the first row, and `l` if you see the instrument's light come
   on.
7. Wait until the arm has gone home by itself and stands still.
8. Save the measurement in both forms (section 7), named `IO3-B05`.
9. Type `IO3-B05 end`.
10. Note: how many rows, read in which direction (all the same way, or back
    and forth), was any row read twice, what the arm did at the end, how long
    the whole sheet took on your clock.

### B06. Sheet S read patch by patch, to its normal end (about 15 min)

**Label:** `IO3-B06`. **This tells us** the patch by patch (spot) reading: the
move to each patch, the head going down and up, the time per patch.

1. Leave Sheet S where it lies.
2. In i1Profiler choose **patch by patch** (spot) reading for the table, if
   it offers it (note the name). If it does not, skip this block and note
   that.
3. Type `IO3-B06 start`.
4. Start the measurement, calibrate if it asks, aim as it asks.
5. For the first 5 patches, type `d` each time the head goes down and `u`
   each time it goes up.
6. Let it read the whole sheet. Do not cancel.
7. Wait until the arm is home and still. Save the measurement as `IO3-B06`.
8. Type `IO3-B06 end`.

### B07. Cancel in the middle of a row, then quit (about 10 min)

**Label:** `IO3-B07`. **This tells us** what i1Profiler sends when a
measurement is cancelled while the arm is out (on the i1iO 2 this was
different from the normal end), and what it sends when it quits.

1. Leave Sheet S where it lies, scanning mode again.
2. Type `IO3-B07 start`.
3. Start the measurement, aim as it asks.
4. When the arm starts along the **second** row, press **Cancel** in
   i1Profiler. Type `a` at that moment.
5. Note what the arm does. Wait until it stands still.
6. Quit i1Profiler normally. Wait 10 seconds.
7. Type `IO3-B07 end`.

**End of Part 1.** Type `e` and finish the run (section 7, steps 7 to 9).
Thank you: this run alone is worth sending.

---

## 9. Part 2: every state the table can be left in

**ESSENTIAL. One run, about 60 minutes. Sheets: S.** This part teaches
ChromIQ how to get the table back to normal **without i1Profiler**, whatever
an earlier session left behind: a measurement that was never finished, a
program that was closed or crashed, the table switched off at a bad moment.
On the first table, the gaps here were the most expensive ones.

Start a new run (section 7). The table is on, i1Profiler is closed, the arm
is at rest.

### B08. Quit i1Profiler while it waits for you to aim (about 8 min)

**Label:** `IO3-B08`. **This tells us** what the table reports when it was
left in its aiming mode (the arm free for your hand), and how i1Profiler gets
it back when it starts again.

1. Type `IO3-B08 start`.
2. Start i1Profiler, start a measurement of Sheet S, and go on until it asks
   you to aim at the **first** point. Do not aim.
3. Quit i1Profiler now (its menu, Quit or Exit; confirm if it asks). Note
   what the arm does, and whether it is free to move by hand (try very gently;
   do not push).
4. Wait 20 seconds.
5. Start i1Profiler again. Note what the arm does when it finds the table.
6. Quit i1Profiler again. Wait 10 seconds.
7. Type `IO3-B08 end`.

### B09. Quit i1Profiler while the arm is out over the sheet (about 8 min)

**Label:** `IO3-B09`. **This tells us** the state of a table whose program
went away in the middle of a measurement, with the arm held out, and the way
home from there.

1. Type `IO3-B09 start`.
2. Start i1Profiler and a measurement of Sheet S (scanning mode), aim, and let
   it read the first row.
3. As soon as the **second** row has finished, quit i1Profiler (do not press
   Cancel first). Confirm if it asks. Note what the arm does.
4. Wait 20 seconds. Start i1Profiler again and note what the arm does.
5. Quit i1Profiler. Type `IO3-B09 end`.

### B10. Force-quit i1Profiler during a row (about 8 min)

**Label:** `IO3-B10`. **This tells us** what the table does when its program
disappears without saying goodbye (as after a crash), during a movement.

1. Type `IO3-B10 start`.
2. Start a measurement of Sheet S (scanning mode), aim, and let the first row
   start.
3. While the arm moves along the row, force-quit i1Profiler: on Windows with
   the Task Manager (select i1Profiler, "End task"); on a Mac with
   Apple menu > Force Quit. Type `a` at that moment.
4. Note what the arm does: does it finish the row, stop, go home, wait? Wait
   30 seconds and note it again.
5. Start i1Profiler again and note what the arm does.
6. Quit i1Profiler normally. Type `IO3-B10 end`.

### B11. The arm moved by hand, then i1Profiler started (about 15 min)

**Label:** `IO3-B11`, with a letter for each place: `IO3-B11a`, `IO3-B11b`, and
so on. **This tells us** how X-Rite's software brings the arm home from each
part of the bed (on the first table it took a detour from one side, and from
the strip beside the white tile), and whether the table pulls a pushed arm
back by itself.

For each place below: the table is on, i1Profiler is closed, the arm at rest.

1. Type the label with its letter and `start`, for example `IO3-B11a start`.
2. Gently move the arm by hand to the place. **If it does not move easily, do
   not push**: note "does not move" and go to the next place. If it moves back
   by itself, let go and note that.
3. Note where it stands (for example "about 15 cm out, near the left edge").
4. Start i1Profiler. Note exactly what the arm does: straight home, or first
   somewhere else, then home.
5. Quit i1Profiler. Type the label and `end`.

The places:

- **a**: a little way out from the resting place, about 5 cm, straight
  towards you;
- **b**: the far left of the bed (your left as you stand in front of the
  table), halfway out;
- **c**: the far right, halfway out;
- **d**: the front left corner (nearest you, on your left);
- **e**: the front right corner;
- **f**: the strip beside the white calibration tile (or wherever the arm
  calibrates), as far to the side as it will go without force;
- **g**: if the arm moves by hand while the table is on and i1Profiler is
  closed: push it about 5 cm out and let go. Does it go back by itself?
  Wait 30 seconds before you start i1Profiler.

### B12. Cold start with the arm out, and without the instrument (about 10 min)

**Label:** `IO3-B12a` and `IO3-B12b`. **This tells us** what the table's own
start-up does when the arm was not at rest when it was switched on, and what
happens when the instrument is not in the arm.

**a. Arm out:**

1. Type `IO3-B12a start`.
2. Switch the table **off**. Gently move the arm by hand about 15 cm out
   over the bed (do not force it).
3. Switch the table **on**. Note what the arm does by itself.
4. Start i1Profiler. Note what the arm does. Quit i1Profiler.
5. Type `IO3-B12a end`.

**b. Instrument not in the arm:**

1. Type `IO3-B12b start`.
2. Switch the table off. Take the instrument out of the arm and lay it safely
   aside, still plugged in.
3. Switch the table on. Start i1Profiler. Note what it says and what the arm
   does. Try to start a measurement and note what i1Profiler says.
4. Quit i1Profiler. Switch the table off, put the instrument back in the arm,
   switch the table on.
5. Type `IO3-B12b end`.

### B13. Switched off and on while i1Profiler runs (optional, about 8 min)

**Label:** `IO3-B13a` (idle) and `IO3-B13b` (during aiming). **This tells us**
what i1Profiler does when the table disappears and comes back, and what
state the table reports afterwards (on the first table, the aiming mode
survived a power cycle).

**a. Idle:**

1. Type `IO3-B13a start`. Start i1Profiler and let it find the table.
2. Switch the table off. Wait 10 seconds. Note what i1Profiler says.
3. Switch the table on. Note what i1Profiler does (does it find the table
   again by itself?).
4. Quit i1Profiler. Type `IO3-B13a end`.

**b. During aiming:**

1. Type `IO3-B13b start`. Start a measurement of Sheet S and go on until it
   asks you to aim.
2. Switch the table off. Wait 10 seconds. Switch it on.
3. Note what i1Profiler says. If it can go on, follow it; if not, cancel or
   quit.
4. Start i1Profiler again if you quit it, and note what the arm does.
   Quit it. Type `IO3-B13b end`.

### B14. The USB cable pulled during a measurement (optional, about 8 min)

**Label:** `IO3-B14`. **This tells us** what the table does when the computer
disappears in the middle of a movement, and how i1Profiler takes it up again.

1. Type `IO3-B14 start`.
2. Start a measurement of Sheet S (scanning mode), aim, and let the first row
   start.
3. During the **second** row, pull the table's USB cable out of the computer.
   Type `a` at that moment.
4. Note what the arm does. Wait 30 seconds. Note what i1Profiler says.
5. Plug the cable in again. Note what i1Profiler does.
6. If the arm does not come to rest by itself within a minute, switch the
   table off and on.
7. Start or restart i1Profiler, let it find the table, quit it.
8. Type `IO3-B14 end`.

**End of Part 2.** Type `e` and finish the run.

---

## 10. Part 3: the whole bed, the vendor's speed, the conditions

**IMPORTANT. One or two runs, about 2.5 to 3 hours. Sheets: S, S-cut, F, L, P,
plain sheets.** This part makes sure ChromIQ never needs "another round"
for a place on the bed, a patch size, a speed or a condition: it records the
whole range i1Profiler itself uses. If you split it into two runs, a good
place is after B19.

### B15. Aiming everywhere on the bed (about 30 min)

**Label:** `IO3-B15`, with a letter for each place. **This tells us** which
places the arm can reach (your aim points), the moves i1Profiler computes
from them, and how far beyond the aim points it goes for a row.

For each place: lay **Sheet S-cut** there, start a measurement of Sheet S in
scanning mode, aim as i1Profiler asks, let it read the **first row**, then
press **Cancel** and let the arm stop. Type the label and `start` before, and
`end` after. Note where the sheet lay (a photo of the bed is ideal).

- **a**: far left, as far back as it will lie;
- **b**: far right, as far back;
- **c**: far left, at the front (nearest you);
- **d**: far right, at the front;
- **e**: in the middle, turned by a few degrees (about the angle of a sheet
  laid in a hurry);
- **f**: Sheet F (the full page) laid exactly as i1Profiler shows: aim, read
  the first row, cancel.

### B16. An aim point beyond the arm's reach (about 10 min)

**Label:** `IO3-B16`. **This tells us** how i1Profiler refuses a point the
arm cannot reach, and how far the arm can really go.

1. Lay the **plain sheet larger than the bed** (or Sheet F pushed as far
   towards one corner as it will go) so that one corner lies beyond where you
   think the arm can reach.
2. Type `IO3-B16 start`.
3. Start a measurement of Sheet F, and when it asks you to aim, move the arm
   **gently** towards the far corner, as far as it goes **without force**, and
   aim there. Note where it stopped.
4. Note exactly what i1Profiler says. If it refuses, follow its advice once.
   If it accepts, let it read the first row, then cancel.
5. Type `IO3-B16 end`.

### B17. Every patch size and every speed (about 40 min)

**Label:** `IO3-B17`, with a letter for each try. **This tells us** the
speeds i1Profiler uses for each patch length, how long it runs before the
first and after the last patch, and the timing of the light against the move.
On the first table we had only some of these, and ChromIQ first read rows
more slowly than i1Profiler.

For each try: type the label and `start`; start the measurement in scanning
mode with the setting named; aim; let it read **two rows** (or the whole
sheet where it says so); cancel; let the arm stop; type the label and `end`;
note the setting and the time one row took.

- **a**: Sheet F, smallest patches, default speed, the **whole sheet** (do
  not cancel; save the measurement as `IO3-B17a`);
- **b**: Sheet L, largest patches, default speed, two rows;
- **c**: Sheet F with the **fastest** speed setting i1Profiler offers (if it
  offers any speed choice), two rows;
- **d**: Sheet F with the **slowest** speed setting, two rows;
- **e**: Sheet S-cut laid at the **front edge** of the bed, default speed,
  two rows;
- **f**: Sheet S-cut laid at the **left** or **right** edge of the bed,
  default speed, two rows;
- **g**: any other scanning setting i1Profiler offers for the table (an
  accuracy or averaging option, a "measure twice" option): one try each,
  two rows. Note the name of each.

### B18. A row i1Profiler cannot read the first time (about 10 min)

**Label:** `IO3-B18`. **This tells us** what i1Profiler does with a row it
cannot read (on the first table: it read the row again more slowly, then
patch by patch, without asking), which speeds it uses for that, and what it
tells you.

1. Lay a **plain sheet** where Sheet S would lie. With a pencil, mark three
   small crosses where Sheet S's aim points would be (or lay Sheet S, mark
   its aim points lightly on the bed's edge, then swap it for the plain sheet).
2. Type `IO3-B18 start`.
3. Start a measurement of **Sheet S** in scanning mode and aim at the three
   pencil crosses.
4. Let i1Profiler try the first row. Note everything it does: how many times
   it runs along the row, at what pace, whether it changes to patch by patch,
   what it says.
5. When it has given up or moved to the second row, press Cancel.
6. Type `IO3-B18 end`.

### B19. Two pages (about 15 min)

**Label:** `IO3-B19`. **This tells us** what happens between pages: where the
arm goes, what i1Profiler asks, and whether each page is aimed again.

1. Type `IO3-B19 start`.
2. Start a measurement of **Sheet P** in scanning mode. Lay page 1 as asked,
   aim, let it read the whole page.
3. Do what i1Profiler asks for page 2 (lay page 2, aim again if asked). Note
   where the arm is while you change the sheet.
4. Let it read page 2 to the end and go home. Save the measurement as
   `IO3-B19`.
5. Type `IO3-B19 end`.

### B20. Calibrating again: later, and after a long pause (about 20 min, mostly waiting)

**Label:** `IO3-B20a`, `IO3-B20b`. **This tells us** when i1Profiler asks for a
new calibration and how it does a second one in the same session.

1. **a:** Type `IO3-B20a start`. In i1Profiler, start a new measurement of
   Sheet S; if it offers to keep the earlier calibration, keep it and note
   that; if it calibrates, let it. Aim, read one row, cancel. Type
   `IO3-B20a end`.
2. Leave i1Profiler **open** and the table on for **at least an hour**
   (other blocks can run meanwhile; this one only needs the hour to have
   passed since the last calibration).
3. **b:** Type `IO3-B20b start`. Start a measurement of Sheet S again. Note
   whether it asks for a new calibration. Let it calibrate, aim, read one
   row, cancel. Type `IO3-B20b end`.
4. If i1Profiler also allows a calibration on the **instrument's own tile**
   (out of the table), do that once as `IO3-B20c` and note every step it asks.

### B21. Measurement conditions (about 25 min)

**Label:** `IO3-B21`, with a letter for each condition. **This tells us** how
the i1Pro 3 is asked to measure on the table for each condition. By hand, an
i1Pro 3 measures M0, M1 and M2 in one pass; on the table that is still to be
confirmed, and the i1Pro 2 on the first table needed a second pass.

For each condition i1Profiler offers for the table: type the label and
`start`; set the condition; start a measurement of **Sheet S** in scanning
mode; aim; let it read the **whole sheet**; save it as the label; type the
label and `end`. Note exactly how i1Profiler names the setting, and whether
each row was read once or twice.

- **a**: M0;
- **b**: M1;
- **c**: M2;
- **d**: "dual scan" or "M0, M1 and M2 together", if i1Profiler offers such a
  setting for the table;
- **e**: M3 with the **polarisation filter**, only if you own it: fit it as
  X-Rite's manual says, and note what i1Profiler asks;
- **f**: if your instrument is an **i1Pro 3 Plus**: if i1Profiler offers a
  choice of aperture or patch size that depends on it, one try with each
  (note the names).

Then one patch by patch try with M1 or M2, Sheet S, the whole sheet, as
`IO3-B21g`.

### B22. The limits: the largest page, thin and thick media, the sheet hold (about 15 min)

**Label:** `IO3-B22`, with a letter. **This tells us** the extreme positions
i1Profiler ever commands, and whether the height setting and the sheet hold
are commands over USB or only knobs and switches on the table.

- **a, the largest page:** lay Sheet F at the very back and left of the bed,
  start a measurement, aim, read the first row, cancel. Then the same with the
  sheet at the very front and right. (If B15 f already did this, skip it.)
- **b, the height:** if your table has a height or thickness adjustment, type
  `IO3-B22b start`, set it for a thick card (or the thickest it allows), then
  back to plain paper, with i1Profiler open and idle. Note how it is set (a
  knob, a lever, a spacer, a setting in i1Profiler). If i1Profiler has its own
  setting for the media thickness, change it there too and note its name.
  Type `IO3-B22b end`.
- **c, the sheet hold:** with i1Profiler open and idle, type `IO3-B22c start`,
  switch the electrostatic sheet hold on, wait 5 seconds, off, wait 5
  seconds, on again. Note how it is switched (a button on the table, a
  setting in i1Profiler) and whether i1Profiler shows anything. Type
  `IO3-B22c end`.

### B23. Errors, provoked safely (optional, about 15 min)

**Label:** `IO3-B23`, with a letter. **This tells us** how i1Profiler and the
table report a problem, and what they do next.

- **a, no sheet:** start a measurement of Sheet S, aim, then, **while the arm
  stands still** waiting for you (before you confirm the last aim point),
  take the sheet away and confirm. Let it try the first row. Note what it
  says. Cancel.
- **b, instrument out of the arm:** start a measurement of Sheet S and go on
  until it asks you to aim. **While the arm stands still**, take the
  instrument out of the arm. Note what i1Profiler says. Put the instrument
  back, follow what i1Profiler asks, then cancel.
- **c, Stop or Pause:** if i1Profiler offers **Stop**, **Pause** or **Resume**
  during a measurement, use each once during a row of Sheet S, and note what
  the arm does each time. Then let it finish or cancel.
- **d, quit with the arm out:** start a measurement, let it read one row,
  cancel, and while the arm is still out (if it stays out), quit i1Profiler.
  Note what the arm does.

Please never put your hand in the arm's way to stop it, and never lift the
instrument out while the arm moves.

### B24. The reference sheet, read twice (about 25 min)

**Label:** `IO3-B24a`, `IO3-B24b`. **This tells us** i1Profiler's own values
for one sheet, read both ways, so that ChromIQ's readings of the very same
sheet can later be compared patch by patch with them.

1. Lay the **clean copy of Sheet F** (the reference sheet) in the middle.
2. **a:** in scanning mode, M0, default speed, read the whole sheet. Save as
   `IO3-B24a` in both forms.
3. **b:** without moving the sheet, read it **patch by patch**, the whole
   sheet. Save as `IO3-B24b` in both forms.
4. Keep this sheet flat, dry and out of the light afterwards. If ChromIQ
   ever drives your table, it is the sheet we will ask you to read again.

**End of Part 3.** Type `e` and finish the run.

---

## 11. Part 4: extras

**NICE TO HAVE. One run, about 40 minutes.**

### B25. Idle for ten minutes (about 12 min)

**Label:** `IO3-B25`. **This tells us** whether i1Profiler talks to the table
while nothing happens (keeping the connection alive, checking its state), and
what the instrument's light does.

1. Type `IO3-B25 start`. Start i1Profiler and let it find the table.
2. Leave everything alone for **ten minutes**. Note what the instrument's
   light does, and if anything moves.
3. Quit i1Profiler. Type `IO3-B25 end`.

### B26. The computer goes to sleep (optional, about 5 min)

**Label:** `IO3-B26`. **This tells us** what happens to the connection when
the computer sleeps. Only on a computer where the recording survives sleep
(on Windows a new USB address after sleep has cost a tester a whole session,
so do this one **last**, and only if you like).

1. Type `IO3-B26 start`. Start i1Profiler and let it find the table.
2. Put the computer to sleep. Wait one minute. Wake it.
3. Note what i1Profiler says. Start a measurement, aim, read one row, cancel.
4. Quit i1Profiler. Type `IO3-B26 end`.

### B27. The instrument by hand, out of the table (about 10 min)

**Label:** `IO3-B27`. **This tells us** which commands belong to the
instrument and which to the table, by comparing the same instrument by hand
in the same session.

1. Take the instrument out of the arm (table off is fine).
2. Type `IO3-B27 start`.
3. In i1Profiler, measure by hand: calibrate as it asks, scan **one row** of
   Sheet S with the instrument's ruler, then read **one single patch** if
   i1Profiler offers spot reading by hand. Save as `IO3-B27`.
4. Put the instrument back in the arm. Type `IO3-B27 end`.

### B28. A ChromIQ chart measured in i1Profiler (optional, about 15 min)

**Label:** `IO3-B28`. **This tells us** whether ChromIQ's chart for the i1iO
and its import of i1Profiler's result work with your table already (the
route that needs no driving at all).

1. In ChromIQ, switch on Preferences > Beta > "X-Rite i1iO support" (restart
   ChromIQ as it asks), and make a small chart for the i1iO in Create Chart
   (choose the i1iO as the instrument, and your table and instrument if it
   asks). Print it.
2. Type `IO3-B28 start`. In i1Profiler, measure it with the function for a
   chart it did not make (for the i1iO 2 it is called "Measure Chart"): type
   the columns and rows ChromIQ shows beside its chart, aim at the three
   points ChromIQ marks. Save the result.
3. Type `IO3-B28 end`.
4. In ChromIQ, bring the file back with IMPORT in the Measure tab, and note
   what ChromIQ says.

**End of Part 4.** Type `e` and finish the run.

---

## 12. After the blocks: photos, files, a few questions

### Photos (phone is fine)

1. The whole table from above, with the arm at its resting place.
2. The bed's markings (the corner marks, any scale) with **a ruler lying in
   the picture**.
3. The white calibration tile (or the place where the arm calibrates), from
   above and from the side, with the ruler.
4. The arm and the instrument's holder, from the side.
5. The height or thickness adjustment, and the sheet hold button, if there are
   any.
6. i1Profiler's settings pages for the table (screenshots): scanning and spot
   mode, speeds, patch sizes, conditions, page sizes.

**Please do not photograph the labels with serial numbers**, or cover them
before you take the picture.

### A few questions (answer in `notes.txt`; skip what you do not know)

1. Your table's model as printed on it (for example "i1iO 3" or "i1iO for
   i1Pro 3 Plus"), but not its serial number.
2. Your instrument: i1Pro 3 or i1Pro 3 Plus? Do you own the polarisation filter?
3. The i1Profiler version, and your computer's system and version.
4. Which patch sizes and page sizes i1Profiler offered for scanning and for
   patch by patch.
5. Does the table hold the sheet electrostatically? Is it a button, or set in
   i1Profiler?
6. Is the head height set by hand? Down to which thickness, up to which?
7. When something goes wrong, what does the table show (a light, a sound)?
8. Anything that surprised you.

## 13. What to send, and how

**Before you send anything, please look at it.** Everything is in your
`i1iO3-recordings` folder.

1. **One set per run:** on a Mac the `SEND-THIS-<date>.zip` the tool made;
   on Windows the **cleaned copy** of your Wireshark recording (below) and the
   tool's report (the `chromiq-io-probe-<date>.txt` file it saved). Never a
   full recording: not the Wireshark file itself, not a Mac's `-full.pcap`
   files, not a folder whose name ends in `-FULL-do-not-send`. They can hold
   everything else on those USB connections, possibly even what you typed on
   a USB keyboard.
2. **`notes.txt`.**
3. **The saved measurements and the saved charts** (i1Profiler's files and the
   CGATS exports), named after their blocks.
4. **The photos and screenshots.**

**Where:** please open a
[new issue](https://github.com/itsab1989/ChromIQ/issues/new) in the ChromIQ
repository titled "Recordings: X-Rite i1iO 3", and attach the files there (a
zip of the whole folder is fine). The issue about the i1iO 2,
[#129](https://github.com/itsab1989/ChromIQ/issues/129), shows how this went
for the first table.

**An issue is public.** The recordings contain your devices' serial numbers
and calibration data (section 3). If you would rather not post them
publicly, say so in the issue without attaching them, and we will agree a
private way; the tool's README describes one. Please do not send anything by
private mail unless you prefer it.

**On Windows, the cleaned copy:** Wireshark records everything on the USB
connections you selected, so its file is not one to post. The tool makes a
copy that keeps only the X-Rite devices' traffic: run it with `--clean` and
the Wireshark file (its README, section "Running from source", shows the
command); it writes the copy next to the original and says what it removed.
Send that copy. To be honest: `--clean` was made for recordings of handheld
instruments, and it has not been tried yet on a Windows recording of an
i1iO 3. If it says it kept nothing, or very little, please say so in the issue
and keep the original. If we find that a copy lacks the table after a power cycle or
a pulled cable, we will ask you for the original **privately**, never in the
issue.

## 14. What a recording cannot tell us, and what happens next

**What a recording cannot show:**

- what the table's firmware does inside, between the commands;
- what the table does by itself without a command (an arm that goes home by
  itself after a push, for example), except through your notes;
- what the table does at a command i1Profiler never sends (and ChromIQ never
  sends a command i1Profiler did not send);
- where the true ends of the arm's travel are, unless i1Profiler went there.

That is why your notes and photos matter as much as the recordings.

**What happens next:**

1. We decode the recordings and write back on the issue what we found, in
   plain words, and what is still unclear. That can take a while; we do not
   promise dates.
2. If the i1iO 3 speaks the same language as the i1iO 2 (Appendix B says what
   we would look for first), much of ChromIQ's table code can be reused. If it
   does not, it is a new study, and we will say so.
3. Before ChromIQ sends anything to your table, an independent review checks
   every command against your recordings and against physical harm.
4. **The first ChromIQ run on your table will be step by step, with your hands
   away**, as it was for the i1iO 2: ChromIQ explains each step before it
   moves, waits for your "yes", and keeps the power switch as the stop. Only
   what has worked once on your table then runs at full speed.

Nothing in this plan is a promise that ChromIQ will support the i1iO 3. Your
recordings are what makes it possible at all. Thank you.

---

## 15. The one-page checklist

Tick each block as you go. Write the label first in the tool's window, and
one line in `notes.txt` after.

| done | block | label | priority | about |
|---|---|---|---|---|
| [ ] | B01 the report, table idle | `IO3-B01` | ESSENTIAL | 5 min |
| [ ] | B02 start and quit i1Profiler | `IO3-B02` | ESSENTIAL | 5 min |
| [ ] | B03 cold start | `IO3-B03` | ESSENTIAL | 5 min |
| [ ] | B04 calibration | `IO3-B04` | ESSENTIAL | 5 min |
| [ ] | B05 Sheet S in rows, to the end (saved) | `IO3-B05` | ESSENTIAL | 15 min |
| [ ] | B06 Sheet S patch by patch, to the end (saved) | `IO3-B06` | ESSENTIAL | 15 min |
| [ ] | B07 Cancel mid-row, then quit | `IO3-B07` | ESSENTIAL | 10 min |
| [ ] | *finish run 1* | | | |
| [ ] | B08 quit while waiting to aim | `IO3-B08` | ESSENTIAL | 8 min |
| [ ] | B09 quit with the arm out | `IO3-B09` | ESSENTIAL | 8 min |
| [ ] | B10 force-quit during a row | `IO3-B10` | ESSENTIAL | 8 min |
| [ ] | B11 a to g, arm moved by hand, then start | `IO3-B11a` ... `IO3-B11g` | ESSENTIAL | 15 min |
| [ ] | B12 a, b cold start with the arm out / no instrument | `IO3-B12a`, `IO3-B12b` | ESSENTIAL | 10 min |
| [ ] | B13 a, b switched off and on (optional) | `IO3-B13a`, `IO3-B13b` | IMPORTANT | 8 min |
| [ ] | B14 USB cable pulled (optional) | `IO3-B14` | IMPORTANT | 8 min |
| [ ] | *finish run 2* | | | |
| [ ] | B15 a to f, aiming everywhere | `IO3-B15a` ... `IO3-B15f` | IMPORTANT | 30 min |
| [ ] | B16 an aim point beyond reach | `IO3-B16` | IMPORTANT | 10 min |
| [ ] | B17 a to g, every patch size and speed | `IO3-B17a` ... `IO3-B17g` | IMPORTANT | 40 min |
| [ ] | B18 a row that cannot be read | `IO3-B18` | IMPORTANT | 10 min |
| [ ] | B19 two pages (saved) | `IO3-B19` | IMPORTANT | 15 min |
| [ ] | B20 a, b (c) calibrating again | `IO3-B20a`, `IO3-B20b` | IMPORTANT | 20 min |
| [ ] | B21 a to g, conditions (saved) | `IO3-B21a` ... `IO3-B21g` | IMPORTANT | 25 min |
| [ ] | B22 a to c, limits, height, sheet hold | `IO3-B22a` ... `IO3-B22c` | IMPORTANT | 15 min |
| [ ] | B23 a to d, errors (optional) | `IO3-B23a` ... `IO3-B23d` | IMPORTANT | 15 min |
| [ ] | B24 a, b reference sheet (saved) | `IO3-B24a`, `IO3-B24b` | IMPORTANT | 25 min |
| [ ] | *finish run 3* | | | |
| [ ] | B25 idle ten minutes | `IO3-B25` | NICE TO HAVE | 12 min |
| [ ] | B26 computer sleep (optional, last) | `IO3-B26` | NICE TO HAVE | 5 min |
| [ ] | B27 the instrument by hand (saved) | `IO3-B27` | NICE TO HAVE | 10 min |
| [ ] | B28 a ChromIQ chart in i1Profiler (optional) | `IO3-B28` | NICE TO HAVE | 15 min |
| [ ] | *finish run 4* | | | |
| [ ] | photos, screenshots, questions | | | 15 min |
| [ ] | looked at every file, then sent (section 13) | | | |

**Privacy, once more:** recordings hold your devices' serial numbers and
calibration data; an issue is public; never send a `-FULL-do-not-send` folder
or a full Mac recording; on a Mac, switch SIP back on.

---

## Appendix A: why each block is there

Every block answers something the first table we supported (an i1iO 2 with an
i1Pro 2) either taught us from a recording, or made us ask for again later.
"Later" always meant another release and another round with its owner.

| block | what the first table taught us | what ChromIQ needs it for |
|---|---|---|
| B01, B02 | Its identity answers and opening lines were exact and fixed; a second model must be recognised by its own before anything is sent. | Telling the i1iO 3 apart, and deciding whether the i1iO 2's code can be reused. |
| B03 | A just-switched-on table reported its own state and needed a start-up of its own (recorded once in the first round, more cases later). | The cold start, without i1Profiler. |
| B04, B20 | Where to calibrate (the table's tile against the instrument's own) was an open question for days; the answer came from a later recording and a comparison of both. The one-hour validity decides when to calibrate again. | The calibration step, and when to repeat it. |
| B05 | The normal scan of a row was not in the first recordings (every row had fallen back); the aiming geometry was settled only from a later round of three recordings. | Aiming, rows as strips, the end of a job. |
| B06 | Patch by patch: the move, the reading and the pace per patch. | Patch by patch reading at i1Profiler's pace. |
| B07, B23 c, d | i1Profiler's cancel and its quit send different endings from the normal end of a job; they were recorded a week after the first runs. | Every ending leaves a table the next start can take. |
| B08 | A table left in its aiming mode kept that state, and ChromIQ's next start refused it; only a recording of i1Profiler starting on such a table showed the way out. | Recovering that state without i1Profiler. |
| B09, B10 | An ending with the arm held out over the bed left the table in a state nobody had recorded. | Every way a session can end, including a crash. |
| B11 | Homing from anywhere: i1Profiler homed straight from most places but took a detour from one side and from the strip beside the white tile. Both detours were found late, and the first versions refused places no recording had covered. | Going home from every part of the bed, the way the vendor does. |
| B12 | A table switched on with the arm out brought it home in its start-up; an idle table pulled a pushed arm back by itself. Both came from the last round of recordings. | The start-up from any arm position; what to tell the person. |
| B13 | The aiming mode survived a power cycle; this was seen twice and still needs confirming. | Telling the person truthfully what the power switch does and does not reset. |
| B14 | A lost link with a move still waiting needed the power switch; what the table does after the cable comes back was never recorded. | The lost-link page and the way back. |
| B15, B16, B22 a | Places the arm had never been in a recording were first fenced off, although the person could aim there; three correction rounds removed those fences. The true end of travel is still not recorded on any side. | One reach rule from the start, with no fence that has no physical reason. |
| B17 | Row speeds by patch length came from several recordings; with only a few of them, ChromIQ first read rows more slowly than i1Profiler. The run beyond the end patches and the timing of the light against the move set the shortest patch. | Rows at the vendor's speed, and how the readings are placed on the patches. |
| B18 | i1Profiler re-reads a failed row more slowly and then patch by patch, asking nobody; the slower speeds were recorded only for some rows. | Reading a failed row again as the vendor does. |
| B19 | The page change: where the arm waits, and that each page is aimed again. | Several pages in one measurement. |
| B21 | On the i1Pro 2, M1 and M2 needed a second pass with its own speed on the table. The i1Pro 3 measures them in one pass by hand; on the table that is to be confirmed. | The measurement conditions on the table. |
| B22 b, c | The height and the sheet hold were never recorded; ChromIQ's texts only remind the person of them. | Knowing whether they are commands at all. |
| B24 | A reading in a recording can only be checked against the program's own saved result of the same measurement; pairing settled which white reference to use. | Comparing ChromIQ's readings with i1Profiler's on the same sheet. |
| B25, B26 | Not recorded on the first table. | Whether ChromIQ must keep the connection alive. |
| B27 | The table and the instrument were separate USB devices on the first table, meeting only in time. | Separating the table's commands from the instrument's. |
| B28 | The chart-out, measurement-back route worked long before the drive did. | Both routes at the same time. |

## Appendix B: what we assume about the i1iO 3

**Nothing in this appendix is verified by a recording.** It is what we read
in public sources or guess from the i1iO 2, written down so that the first
recording can confirm or correct it.

- **The model.** X-Rite sells the third-generation table for the i1Pro 3 and
  the i1Pro 3 Plus (also in bundles). Whether it is a new mechanism or the
  i1iO 2's mechanism with a new holder and firmware is not known to us.
- **Its USB identity.** The recording tool names the USB ID 0765:30B0 "i1iO 3
  table", taken from a driver file of X-Rite's software. The i1iO 2 is
  0971:2004 (a USB-to-serial chip) and speaks short lines of text. The
  i1Pro 3 is 0765:6009, a separate USB device. Whether the i1iO 3 is one
  device or two, and whether it speaks the same kind of lines, is the first
  thing block B02 will show.
- **The bed.** X-Rite gives a positioning area of 32 x 23 cm for the i1iO 3,
  media up to 10 mm thick, and up to 33 mm with an optional spacer (published,
  not checked by us).
- **Patch sizes.** Retailers quote X-Rite's minimum of 16 x 16 mm in scanning
  mode with the i1Pro 3 Plus, 14 x 14 mm patch by patch, and 16 x 20 mm for
  M3 (published, not checked by us). The i1Pro 3 Plus has an 8 mm aperture.
- **The instrument.** By hand, an i1Pro 3 measures M0, M1 and M2 in one pass
  and reads its ruler on a separate channel; i1Profiler drives its lights
  itself (from an earlier recording of an i1Pro 3 by hand). How it is
  triggered on the table is not known.
- **i1Profiler.** X-Rite says the i1Pro 3 and the i1iO 3 work with current
  Windows 11 releases, unlike the i1Pro 2 and i1iO 2, which the newest
  i1Profiler no longer supports.

Sources for the public figures: X-Rite's product pages for the i1iO for the
i1Pro 3 Plus and the i1Pro 3 Plus specification sheet, as quoted by
retailers; X-Rite's note on i1Pro 2 end of life and Windows 11.
