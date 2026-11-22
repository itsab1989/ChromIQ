# Recording plan for the X-Rite i1iO 3 table

**For owners of an X-Rite i1iO 3 scanning table (the third generation, made for
the i1Pro 3 or the i1Pro 3 Plus) who would like to help ChromIQ learn to drive
it.**

Thank you for reading this. This page is a complete plan for recording what
X-Rite's own software (i1Profiler) says to your table, with our free,
read-only recording tool listening. It is written so that you can follow it
alone, with the table beside you, without knowing anything about programming
or USB.

It is long because it is complete, not because it is hard. Every block is a
short list of single actions, almost all of them in i1Profiler, the way you
use it anyway. The plan is ordered so that **the most useful blocks come
first**: if you stop after Part 1, we already have the core.

This plan is the worked example of
[section 2a of the guide for adding an instrument](adding_an_instrument.md#2a-recording-an-instrument-that-moves).

**Contents**

1. [In short](#1-in-short)
2. [What this is, and what we will do with it](#2-what-this-is-and-what-we-will-do-with-it)
3. [What is recorded, and what is not](#3-what-is-recorded-and-what-is-not)
4. [Safety](#4-safety)
5. [Which computer to record on](#5-which-computer-to-record-on)
6. [What you need](#6-what-you-need)
7. [The sheets to print](#7-the-sheets-to-print)
8. [How to record, step by step](#8-how-to-record-step-by-step)
9. [What the tool says, and what to do instead](#9-what-the-tool-says-and-what-to-do-instead)
10. [Part 1: the core, with the untidy endings (ESSENTIAL)](#10-part-1-the-core-with-the-untidy-endings)
11. [Part 2: every state the table can be left in (ESSENTIAL)](#11-part-2-every-state-the-table-can-be-left-in)
12. [Only if you are comfortable with it (OPTIONAL EXTRAS)](#12-only-if-you-are-comfortable-with-it)
13. [Part 3: the whole bed, the vendor's speed, the conditions (IMPORTANT)](#13-part-3-the-whole-bed-the-vendors-speed-the-conditions)
14. [Part 4: extras (NICE TO HAVE)](#14-part-4-extras)
15. [After the blocks: photos, files, a few questions](#15-after-the-blocks-photos-files-a-few-questions)
16. [What to send, and how](#16-what-to-send-and-how)
17. [What a recording cannot tell us, and what happens next](#17-what-a-recording-cannot-tell-us-and-what-happens-next)
18. [The one-page checklist](#18-the-one-page-checklist)
- [Appendix A: why each block is there](#appendix-a-why-each-block-is-there)
- [Appendix B: what we assume about the i1iO 3](#appendix-b-what-we-assume-about-the-i1io-3)

---

## 1. In short

- **What:** you use your i1iO 3 in i1Profiler as you normally would, plus a
  few things you would normally avoid (cancelling, closing i1Profiler at an
  odd moment, switching the table off), while our recording tool listens to
  the USB cable.
- **Why:** ChromIQ only ever sends a device commands it has seen X-Rite's own
  software send to that very model. Your recordings are where those commands
  come from.
- **How long:** honestly, **about 9.5 hours in all, best over two days**,
  including about an hour of getting ready and one hour in which the table
  simply waits. You can stop after any block.

  | part | what it gives us | priority | time |
  |---|---|---|---|
  | Part 1, B01 to B09 | how the table is recognised, started cold and warm, calibrated, aimed, read in rows and patch by patch, ended cleanly, and recovered by i1Profiler after it was closed without tidying up | ESSENTIAL | about 1.5 h |
  | Part 2, B10 to B15 | every other state a session can leave the table in, and the way home from every part of the bed | ESSENTIAL (B14, B15 optional) | about 1.5 h |
  | Optional extras, X1 to X3 | things done by hand that only the table can answer | OPTIONAL, only if you are comfortable | about 15 min |
  | Part 3, B16 to B25 | the whole bed, every patch length and speed, retries, two pages, the conditions, the limits, a reference sheet, a long pause | IMPORTANT | about 4.5 h, one hour of it waiting |
  | Part 4, B26 to B28 | sleep, the instrument by hand, a ChromIQ chart | NICE TO HAVE | about 30 min |

- **One afternoon instead?** Part 1 and the blocks B10 to B13 of Part 2, with
  getting ready: **about 3 to 3.5 hours**. That already covers every state ChromIQ
  would have to handle without i1Profiler, except the table switched off while
  i1Profiler runs and a pulled cable.
- **Two days?** Day 1: getting ready, Part 1, Part 2. Day 2: Part 3, Part 4,
  photos.
- **Nothing is sent anywhere by itself.** You decide what to send, after you
  have looked at it.
- **Nothing here is a promise** that ChromIQ will be able to drive an i1iO 3.
  It is the first step, and with the first table we supported it was the step
  that decided everything else.

## 2. What this is, and what we will do with it

ChromIQ drives the previous model, the i1iO 2 with an i1Pro 2, itself: it
moves the arm, aims, calibrates and reads a chart in rows or patch by patch,
without i1Profiler. That was learned from recordings like the ones this plan
asks for, made by owners of that table over several rounds.

We learned one thing above all from that work: **every time a recording was
missing, we had to guess, the guess was too careful, and fixing it cost
another round with the owners.** Examples, all from the first table:

- We had recordings of the arm going home only from a few places. So early
  versions refused to bring the arm home from anywhere else, although
  X-Rite's software does it from everywhere.
- Nobody had recorded what X-Rite's software does with a table that a program
  left in its aiming mode without tidying up. When ChromIQ left the table in
  that state, its next start refused the table, and only i1Profiler could get
  it out, until a later recording showed how.
- From two parts of the bed, X-Rite's software goes home by a detour. That
  came only from recordings made after the first real runs.
- We had the speeds for some patch lengths only, so ChromIQ first read rows
  more slowly than i1Profiler does.

So this plan asks for **everything at once**: every way of starting, every way
of ending (the tidy ones and the untidy ones), the whole bed, every patch
length. Then the first ChromIQ version for your table can do what i1Profiler
does, at i1Profiler's speed, from the start.

**What we do with the recordings:**

1. Read every command i1Profiler sent and every answer the table gave, with
   the time of each, and match them to your notes.
2. Write down, in our own words, what each command does, how long each move
   takes, and which states the table reports.
3. Build a simulated table from that, and test ChromIQ's code against it
   (thousands of runs, with every kind of fault), long before anything is sent
   to a real table.
4. Only then, and only if the recordings show that it can work, offer you a
   first ChromIQ version for your table, step by step, with your agreement
   before every step (section 17).

ChromIQ can already make charts for the i1iO tables and bring back the
measurement i1Profiler made of such a chart (Preferences > Beta, "X-Rite i1iO
support"). That keeps working whatever comes of this plan.

## 3. What is recorded, and what is not

**The recording tool** is the "ChromIQ X-Rite instrument probe", free and open
source:
[github.com/itsab1989/chromiq-i1io-probe](https://github.com/itsab1989/chromiq-i1io-probe).
Its README is the full manual; section 2 of
[the guide](adding_an_instrument.md#2-you-own-an-instrument-chromiq-does-not-support-yet-this-is-how-you-can-help)
summarises it. In short:

- **It never sends anything to the table or the instrument**, not one byte,
  and it never opens a connection to them. It only listens.
- **On a Mac** it records with the system's own `tcpdump`, which works only
  while System Integrity Protection (SIP) is fully switched off (section 5).
  It then keeps a copy with only the X-Rite devices' traffic, and puts it
  into one `SEND-THIS-<date>.zip`.
- **On Windows** (a PC with an Intel or AMD processor) the table session of
  version 1.6.6 does not record by itself: you record with Wireshark and its
  USBPcap part while the tool notes the time of every block (section 5).
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
  keyboard and a mouse may stay. And please do not type anything private while
  a recording runs: the full recording (never the copy you send) can hold what
  you type on a USB keyboard.

**What we never do with it:** we never put a recording, a serial number,
calibration data or anything read from your devices into ChromIQ's code or
tests. Only conclusions in our own words (a speed, a command form, a time) go
into the project, with a note of where they came from. We never take X-Rite's
software apart; we only look at what it says over the cable.

## 4. Safety

**Parts 1 to 4 are done in X-Rite's own software, and the arm goes only where
i1Profiler puts it** (or where you put it yourself while i1Profiler has
released it for aiming, exactly as you do when you aim). The recording tool
cannot move anything. A few blocks do something you would normally avoid:
closing i1Profiler forcibly, switching the table off and on, switching it off
while i1Profiler runs, pulling the USB cable. These are ordinary things that
also happen by accident; the last two are marked **optional**.

Things done **by hand on the table** that i1Profiler does not ask for (pushing
the arm while the table is on, switching on with the arm out, taking the
instrument out) are **not** part of the normal blocks. They are in their own
section, [Only if you are comfortable with it](#12-only-if-you-are-comfortable-with-it),
each with what we know and when to skip it. We can work without them.

**X-Rite's own instructions come first.** We could not read X-Rite's website
while writing this plan. Wherever this plan disagrees with X-Rite's manual or
the quick start guide that came with your table, please follow X-Rite, skip
our block, and tell us.

Before you start, please read these four lines once:

1. **The table's power switch is the emergency stop.** Switching it off
   should stop the arm at once; on the i1iO 2 it did. Know where it is before
   Part 1.
2. **Keep your hands away from the arm while it moves.** Touch the arm only
   when i1Profiler asks you to aim, or when a block says the arm is free.
3. **Never force the arm.** If it does not move at the lightest touch, it is
   being held by its motors: let go, and skip that part.
4. **Only your sheet on the bed.** No rulers, tape or tools on the table while
   it measures.

One more honest note: i1Profiler itself writes a small record into an i1Pro 3
during normal use (an earlier recording of an i1Pro 3 by hand showed it). That
is X-Rite's own behaviour and happens whenever you use i1Profiler. ChromIQ
never copies such a write.

## 5. Which computer to record on

Use the computer you already run i1Profiler on with this table. Neither way
is effortless today; here is what each costs.

**On a Mac:**

- SIP must be fully off while you record. Switching it off takes two restarts
  (one into the Mac's startup options, one back), and switching it on again
  takes two more: about 10 to 15 minutes each time. The tool's README shows
  the steps for Apple Silicon and Intel Macs.
- While SIP is off, macOS protects its own system files less well. Keep it off
  only for the recording and **switch it on again at the end of each sitting**,
  then check it: open Terminal, type `csrutil status`, and it should say
  "enabled".
- So: **one sitting = one SIP-off period.** The two-day route costs two
  sittings (eight restarts in all); the one-afternoon route one sitting (four
  restarts). Doing every part on its own day would cost four sittings.
- In return, the tool does the rest itself: it records, checks every block as
  you go, makes the X-Rite-only copy and the one zip to send.

**On Windows (a PC with an Intel or AMD processor):**

- Nothing in Windows' security needs switching off, but Wireshark must be
  installed with its USBPcap part (a restart afterwards), started by hand for
  every run, with every USBPcap entry selected, and its recording saved at the
  end of every run.
- The tool cannot check the blocks as you go (it cannot see Wireshark's file),
  so a block that recorded nothing shows up only afterwards.
- Wireshark's file holds everything on those USB connections, so before you
  send it you make a cleaned copy with one command (section 16).
- This route is for owners who are comfortable with Wireshark. If you are not,
  record on a Mac, or tell us in an issue: a version of the tool that records
  the table on Windows by itself is on our list, and we can wait for it.

Windows on ARM, and a Windows virtual machine on an Apple Silicon Mac, cannot
record at all.

## 6. What you need

- [ ] **The i1iO 3 table**, with its power cable and its USB cable.
- [ ] **The instrument** on it: an i1Pro 3 or an i1Pro 3 Plus. If you have the
      polarisation filter for it, keep it at hand (block B21).
- [ ] **i1Profiler**, the version you normally use, already able to see the
      table. Please **write down its version** (in i1Profiler's Help or About
      window) and **do not let it update itself** during the plan.
- [ ] **The recording tool, version 1.6.6 or newer**, from its
      [latest release](https://github.com/itsab1989/chromiq-i1io-probe/releases/latest):
      one file for your system (on Windows `chromiq-io-probe-windows.exe`, on
      a Mac `chromiq-io-probe-macos`).
- [ ] **On Windows:** Wireshark with its USBPcap part (from wireshark.org;
      tick "USBPcap" in its installer, then restart Windows).
      **On a Mac:** SIP switched off for the sitting (section 5).
- [ ] **The sheets of section 7**, printed in i1Profiler.
- [ ] **A ruler** in millimetres, and **a phone camera** for a few photos.
- [ ] **A plain text file `notes.txt`** in a new folder, for example
      `i1iO3-recordings` on your desktop.
- [ ] **A clock showing seconds** (the computer's clock is fine).
- [ ] **Time**: about 1.5 hours for Part 1. The rest can follow.

## 7. The sheets to print

Please make every chart in **i1Profiler's own test chart step** for the i1iO 3
(in the printer profiling workflow), with your instrument chosen. That way
i1Profiler measures charts it made itself, which is the normal use we want to
record. Colour does not matter much for most blocks: any printer and any plain
paper that the table holds flat is fine.

**The patch size** is set where i1Profiler lays out the chart (a patch size or
patch width and height field, or a slider). Each time, please **write the
value it shows into `notes.txt`**, with the sheet's name.

**Please save each chart in i1Profiler** (it offers its own chart file, for
example a `.pxf` or `.txf` file, or the whole workflow, a `.pwxf` file), and
write its file name into `notes.txt`.

| name | what to make in i1Profiler | copies | used in |
|---|---|---|---|
| **Sheet S** (small) | 3 rows of about 10 to 12 patches, at the **smallest patch size** i1Profiler offers for scanning, on an ordinary A4 or Letter page. | 2. Cut one copy down to the printed area plus about 2 cm on every side: **Sheet S-cut**. | Parts 1, 2, 3 |
| **Sheet F** (full page) | As many patches as fit one page at the smallest patch size, on the **largest page size** i1Profiler offers for the i1iO 3 (note which it is). | 2. Keep one clean, flat and out of the light: the **reference sheet** of B24. | B16f, B17, B24 |
| **Sheets R1 to R5** (patch lengths) | Five small charts of **2 rows** each, at **five patch sizes spread over the whole range** i1Profiler offers for scanning: the smallest (R1), the largest (R5), and three between them, as evenly spaced as it allows. If it offers fewer than five sizes, one sheet per size it offers. | 1 each | B18 |
| **Sheet P** (two pages) | A chart with more patches than fit one page, so that i1Profiler lays it out on **two pages**. | 1 of each page | B20 |
| **Plain sheets** | Plain paper, unprinted: three A4 or Letter sheets, and one sheet **larger than the bed** (A3 or Tabloid) if you have one. | | B17, B19 |

Please also note the whole list of patch sizes i1Profiler offers for scanning,
the smallest and largest it allows for patch by patch reading, and whether it
offers a function for measuring a sheet it did not make itself (for the
i1iO 2 it is called "Measure Chart").

## 8. How to record, step by step

The plan is split into **runs**. One run is one start of the recording tool,
from its start to its end; each Part is one run. Inside a run, **each block is
its own "take"** of the tool's step 1: the tool stores when the take started
and ended, asks you for a one-line note, and (on a Mac) checks the recording
right after it.

### Starting a run

1. **Unplug every other USB device you can** (section 3).
2. **The table is on and plugged in, i1Profiler is closed.** The blocks say
   when to start it.
3. **Start the recording tool.** On Windows: right-click it, "Run as
   administrator". On a Mac: in Terminal, as its README says, with SIP off.
4. It looks for your instruments, then asks what you would like to do.
   Choose **1. record an i1iO table**.
5. It asks three short questions: answer **i1iO 3**, your instrument
   (**i1Pro 3** or **i1Pro 3 Plus**), and your i1Profiler version.
6. **On Windows:**
   - look for the line "USB recorder attached". Only "yes" means the
     recording can see your table. If it says "no", follow what it says
     (usually: unplug the table, restart Windows with "Restart", plug it in
     again, start the tool again);
   - start **Wireshark**, select **all** USBPcap entries (hold Ctrl and click
     each one). If the gear icon beside an entry offers "Inject already
     connected devices descriptors into capture data" or capturing from
     newly connected devices, tick them. Start recording;
   - when the tool asks "Is the recording running? Shall I start the
     walkthrough?", answer yes.
7. **On a Mac:** when the tool asks "Start the recording now?", answer yes,
   and type your password when macOS asks for it (nothing appears while you
   type).
8. The tool now shows "STEP 1 of 5" with its own text. **Ignore its text**
   (section 9) and go on below.

### One block = one take

1. Press **Enter** to start the take.
2. Type the block's **label**, for example `IO3-B05`, and press Enter.
3. Do the block's steps.
4. While you do them, note events in the tool's window as they happen: click
   into it, type, press Enter. Each line is kept with its exact time.
   - Four single letters have fixed meanings, and only these: `a` = the arm
     starts moving, `l` = the instrument's light comes on, `d` = the head goes
     down, `u` = the head goes up.
   - For everything else, type a word: `cancel`, `quit`, `killed` (after a
     force-quit), `power off`, `power on`, `pulled` (the cable), `plugged`,
     `home` (the arm arrived at its resting place), `calibrating`, `message`
     (i1Profiler showed a message), or a few words of your own.
5. When the block is done and the arm stands still, type **`e`** and press
   Enter. The take ends.
6. The tool asks for **one line** about the take: type what you saw the arm
   do, for example `went along each row, left to right, then straight home`.
7. **On a Mac** the tool now shows a CHECK line (section 9 says what each one
   means).
8. Type **`r`** and press Enter: the next take starts at point 1, for the next
   block. (The tool calls it "take 2", "take 3" and so on; that is expected,
   and there is no limit.)
9. After the **last** block of the run, type **`q`** instead of `r`.

**If a block went wrong** (you pressed the wrong button, the CHECK says the
recording has stopped): finish the take with `e`, type `r`, and do the same
block again in the new take, with its label and the word `again`, for example
`IO3-B05 again`. Only that block is repeated.

**Three things to avoid in the tool's window:** typing only `e`, `end` or
`done` before the block is finished (that ends the take); typing `a`, `l`,
`d` or `u` for anything other than their meaning; pressing Ctrl-C (it ends the
run; what was recorded until then is kept). And after a click in i1Profiler,
click into the tool's window again before you type, so that your keys land in
the tool and not in i1Profiler.

**`notes.txt`, a second record:** after each block, write one line there too:
the label, the clock time **to the second**, and what you saw. For example
`IO3-B05 14:32:10 rows left to right, head down at each row start, straight home, "Measurement complete"`.
On Windows the tool keeps its times in memory until the run ends, so if its
window is closed by accident, `notes.txt` is the only record of that run.

**Measurements: save each one.** Whenever a block measures something, save it
in i1Profiler **in two forms**, named after the label (for example `IO3-B05`):
i1Profiler's own measurement file, and an export as a **CGATS text file
(`.txt`) with the spectral data** if i1Profiler offers it. A recording paired
with i1Profiler's own result of the same measurement tells us far more than
either alone, and a measurement from another session cannot be paired later.

**If something unexpected happens** (an error you did not provoke, the arm
does something odd): that is a result, not a failure. Note it, let the table
come to rest, and go on with the next block. If the table seems stuck, switch
it off at its power switch, note `power off`, and go on.

### Ending a run

1. After `q`, the tool asks "Anything odd happen?": type a line or press
   Enter.
2. **On a Mac** it stops recording, switches its recording interfaces off,
   makes the X-Rite-only copy and writes one `SEND-THIS-<date>.zip`. It offers
   to delete the full recordings: please answer **no** for now and keep them
   until we have looked at what you sent (some blocks switch the table off or
   unplug it, and we want to be able to check that the copy kept everything).
   **Never send the full recordings.**
3. It asks a few questions about the chart and the settings: answer briefly,
   or press Enter to skip. `notes.txt` covers the rest.
4. **On Windows:** stop Wireshark and save the recording (File > Save As) into
   your `i1iO3-recordings` folder, named after the run, for example
   `run1-part1.pcapng`. Keep the tool's report (`chromiq-io-probe-<date>.txt`)
   beside it.
5. **On a Mac, at the end of the sitting:** switch SIP back on and check it
   with `csrutil status` (section 5).

## 9. What the tool says, and what to do instead

Version 1.6.6 of the tool was written with the i1iO 2 in mind. Some of what it
shows does not fit an i1iO 3 or this plan:

| the tool says | what to do |
|---|---|
| "Before you start: open i1Profiler and let it find the table", and in its list "i1Profiler is open and has found the table" (Mac) | Keep i1Profiler **closed** when a run starts. The blocks say when to start it. |
| "IMPORTANT FOR OWNERS OF AN i1Pro 2 OR AN i1iO 2: ... stay on i1Profiler 3.8.6 or older" | Not for the i1iO 3. Use the i1Profiler you have; just do not let it update during the plan. |
| "up to five short steps ... about 30 minutes", and "WHAT YOU WILL DO (5 short steps ...)" | That was for the i1iO 2. This plan replaces those steps. |
| "STEP 1 of 5: One row of a chart that scans in one pass", with its own instructions | Ignore its instructions. Each take of step 1 is one block of this plan. |
| "(take 2)", "(take 3)" ... in the step's title | Expected: one take per block. |
| CHECK: "the recording holds N packets from the i1iO 3. Its protocol is not known yet, so this step cannot be checked here: please just carry on." | N counts **every** i1iO 3 packet since the run began, not only this take's. So write N down after each take: if it is **larger** than after the take before, the table was recorded in this take; carry on. If it is **not larger**, this take recorded nothing of the table: do that block again in a new take (with `again`). |
| CHECK: "no table command was recorded in this step: please repeat it" | The tool did not see the i1iO 3 under the USB number it expects. That is itself something we need to know: note it in `notes.txt` and carry on (no need to repeat). |
| CHECK: "the recording on ... has stopped, so nothing more is being recorded" | The recorder ended (for example after a power cycle or sleep). Type `q`, end the run, start a new run, and do that block again. |
| (Windows) no CHECK line at all | Expected: on Windows the tool cannot see Wireshark's file. |
| "Still missing: ... run the tool again now" | Written for the i1iO 2's five steps. Ignore it. |
| "for the i1iO table: attach it to" issue #129 | For the i1iO 3, open the new issue of section 16 instead. |

## 10. Part 1: the core, with the untidy endings

**ESSENTIAL. One run, about 1.5 hours. Sheet S.** After this part alone we
know how the table is recognised and started, how it calibrates, aims and
reads a page in rows and patch by patch, how i1Profiler ends a job and quits,
**and how it recovers a table that a program left without tidying up**. That
last part is what ChromIQ needs to work without i1Profiler.

Start a run (section 8). The table is on, i1Profiler closed, the arm at rest.

### B01. The table idle (about 5 min)

**Label:** `IO3-B01`. **This tells us** which USB devices the table and the
instrument are (the tool's report lists them), which decides almost
everything else.

1. Start the take, type the label.
2. Wait 30 seconds and touch nothing.
3. End the take with `e`. In the one-line note: where the arm stands (its
   resting place), whether the instrument is in the arm, any light on the
   table.

### B02. Start and quit i1Profiler, table already on (about 5 min)

**Label:** `IO3-B02`. **This tells us** how i1Profiler finds the table and the
instrument, the first commands and answers, and how it lets go of them when it
quits.

1. Start the take, type the label.
2. Start i1Profiler. Wait until it shows that it has found the table and the
   instrument, and 20 seconds more. Touch nothing.
3. Quit i1Profiler normally (its menu, Quit or Exit). Type `quit`.
4. Wait until it has closed, and 10 seconds more. End the take.

### B03. Cold start: the table switched on while recording (about 5 min)

**Label:** `IO3-B03`. **This tells us** what a just-switched-on table reports
and the start-up i1Profiler then sends (on the i1iO 2 a just-switched-on table
needed its own start-up).

1. Start the take, type the label.
2. Switch the table **off** at its power switch (`power off`). Wait 10 seconds.
3. Switch it **on** (`power on`). Wait until it is quiet. Note whether the arm
   moves by itself.
4. Start i1Profiler. Wait until it has found the table. Note what the arm does.
5. Quit i1Profiler (`quit`). Wait 10 seconds. End the take.

### B04. Calibration on the table (about 5 min)

**Label:** `IO3-B04`. **This tells us** where the instrument is calibrated, how
the arm gets there and back, and what i1Profiler asks of you.

1. Start the take, type the label.
2. Start i1Profiler and choose a measurement of Sheet S on the table, up to
   the point where it calibrates (usually the first thing it does when you
   start a measurement). Type `calibrating` when it starts.
3. Let it calibrate, exactly as it asks. Note **where** it calibrates (on a
   white reference on the table, in the instrument's holder, elsewhere) and
   what it asks you to do.
4. If it then goes on to aiming, press **Cancel** (`cancel`) and let the arm
   come to rest. Leave i1Profiler open. End the take.

### B05. Sheet S read in rows, to its normal end (about 15 min)

**Label:** `IO3-B05`. **This tells us** the whole normal measurement: the
aiming, the moves, the scan of each row with its speed, how reading and
movement are timed against each other, the way home and the end of the job.

1. Lay Sheet S in the **middle** of the bed, as i1Profiler shows. If your
   table has a sheet hold (an electrostatic mat with a button), switch it on
   as you normally would, and note it.
2. In i1Profiler set up the measurement of Sheet S in **scanning mode** (rows
   read as strips; note the exact name i1Profiler uses), with its **default
   speed** and **M0** (or its default condition).
3. Start the take, type the label.
4. Start the measurement. Let it calibrate if it asks.
5. **Aim** at the points it asks for, exactly as it asks. Note how many points
   and which, and whether you confirm each with the **instrument's button** or
   with a click on the screen (use the button if it allows both).
6. Let it read the whole sheet. **Do not cancel.** Type `a` when the arm
   starts along the first row, and `l` if you see the instrument's light come
   on.
7. Wait until the arm has gone home by itself and stands still (`home`).
8. Save the measurement in both forms, named `IO3-B05`. End the take.
9. In the one-line note: rows read in which direction (all the same way, or
   back and forth), any row read twice, what the arm did at the end, how long
   the sheet took.

### B06. Sheet S read patch by patch, to its normal end (about 15 min)

**Label:** `IO3-B06`. **This tells us** the patch by patch (spot) reading: the
move to each patch, the head going down and up, the time per patch.

1. Leave Sheet S where it lies. In i1Profiler choose **patch by patch** (spot)
   reading for the table, if it offers it (note the name). If it does not,
   skip this block and note that.
2. Start the take, type the label.
3. Start the measurement, calibrate if it asks, aim as it asks.
4. For the first 5 patches, type `d` each time the head goes down and `u` each
   time it goes up.
5. Let it read the whole sheet. Do not cancel. Wait until the arm is home and
   still (`home`).
6. Save the measurement as `IO3-B06`. End the take.

### B07. Cancel in the middle of a row, then quit (about 10 min)

**Label:** `IO3-B07`. **This tells us** what i1Profiler sends when a
measurement is cancelled while the arm is out (on the i1iO 2 this differed
from the normal end), and what it sends when it then quits.

1. Sheet S where it lies, scanning mode again.
2. Start the take, type the label.
3. Start the measurement, aim as it asks.
4. When the arm starts along the **second** row, press **Cancel** in
   i1Profiler and type `cancel`.
5. Note what the arm does. Wait until it stands still.
6. Quit i1Profiler normally (`quit`). Wait 10 seconds. End the take.

### B08. Force-quit i1Profiler while it waits for you to aim, then start it again (about 12 min)

**Labels:** `IO3-B08a`, `IO3-B08b` (two takes). **This tells us** the state a
table is in when its program disappeared while the arm was released for
aiming, and **how i1Profiler repairs that state when it starts again**. On the
i1iO 2 this was the state ChromIQ's untidy endings left behind, and the most
expensive one to have missed.

To force-quit: on Windows open the Task Manager (Ctrl+Shift+Esc), select
i1Profiler and press "End task"; on a Mac choose Apple menu > Force Quit,
select i1Profiler and press Force Quit.

**a. The arm left where i1Profiler released it:**

1. Start the take, type `IO3-B08a`.
2. Start i1Profiler, start a measurement of Sheet S, and go on until it asks
   you to aim at the **first** point. Do not aim, do not touch the arm.
3. Force-quit i1Profiler. Type `killed`.
4. Note what the arm does (probably nothing). Wait 20 seconds.
5. Start i1Profiler again. Note exactly what the arm does when it finds the
   table (straight home? first somewhere else?).
6. Quit i1Profiler normally (`quit`). Wait 10 seconds. End the take.

**b. The free arm moved before the restart:**

1. Type `r` for the next take, start it, type `IO3-B08b`.
2. As in a, go on until i1Profiler asks you to aim at the first point, then
   force-quit it (`killed`).
3. **If the arm still moves as freely as it does while you aim**, move it
   gently, as you would to aim, to the **middle** of the bed. If it does not
   move at the lightest touch, leave it and note that.
4. Note where it stands. Wait 20 seconds.
5. Start i1Profiler again. Note exactly what the arm does.
6. Quit i1Profiler normally (`quit`). End the take.

### B09. Force-quit i1Profiler during a row, then start it again (about 10 min)

**Label:** `IO3-B09`. **This tells us** what the table does when its program
disappears during a movement (as after a crash), what state it is left in with
the arm held out over the sheet, and how i1Profiler brings it back.

1. Start the take, type the label.
2. Start a measurement of Sheet S (scanning mode), aim, and let the first row
   start.
3. While the arm moves along the row, force-quit i1Profiler. Type `killed`.
4. Note what the arm does: does it finish the row, stop, go home, wait? Wait
   30 seconds and note it again.
5. Start i1Profiler again and note what the arm does.
6. Quit i1Profiler normally (`quit`). End the take.

**End of Part 1.** Type `q` and end the run (section 8). On a Mac, if you stop
here for the day, switch SIP back on. Thank you: this run alone is worth
sending.

---

## 11. Part 2: every state the table can be left in

**ESSENTIAL. One run, about 1.5 hours. Sheets S and S-cut.** B14 and B15 are
optional: essential to us if you are willing, and fine to skip.

Start a new run. The table is on, i1Profiler closed, the arm at rest.

### B10. Quit normally while i1Profiler waits for you to aim (about 6 min)

**Label:** `IO3-B10`. **This tells us** how i1Profiler tidies up when it quits
at this point. On the i1iO 2 its normal quit always put the table back in
order; that tidy-up is the design ChromIQ copies for its own endings.

1. Start the take, type the label.
2. Start a measurement of Sheet S and go on until it asks you to aim at the
   first point. Do not aim.
3. Quit i1Profiler normally (its menu; confirm if it asks). Type `quit`.
4. Note what the arm does. Wait 20 seconds.
5. Start i1Profiler again, note what the arm does, quit it. End the take.

### B11. Quit normally with the arm out over the sheet (about 6 min)

**Label:** `IO3-B11`. **This tells us** how i1Profiler tidies up when it quits
in the middle of a measurement, with the arm held out.

1. Start the take, type the label.
2. Start a measurement of Sheet S (scanning mode), aim, and let it read the
   first row.
3. As soon as the **second** row has finished, quit i1Profiler normally (do
   not press Cancel first; confirm if it asks). Type `quit`.
4. Note what the arm does. Wait 20 seconds.
5. Start i1Profiler again, note what the arm does, quit it. End the take.

### B12. The aiming mode across a power cycle (about 10 min)

**Label:** `IO3-B12`. **This tells us** whether the table still reports its
aiming mode after it was switched off and on with no program running, and the
start-up i1Profiler then sends. On the i1iO 2 this was seen, but never
confirmed.

1. Start the take, type the label.
2. As in B08a: start a measurement of Sheet S, go on until it asks you to aim,
   then force-quit i1Profiler (`killed`). Do not touch the arm.
3. Switch the table **off** (`power off`). Wait 10 seconds. Switch it **on**
   (`power on`). Note what the arm does by itself. Wait until it is quiet.
4. Start i1Profiler (no program has run since the power cycle). Note what the
   arm does when it finds the table.
5. Quit i1Profiler normally (`quit`). End the take.

### B13. The way home from every part of the bed (about 35 min)

**Labels:** `IO3-B13a` to `IO3-B13g`, one take each. **This tells us** how
X-Rite's software brings a held arm home from each part of the bed. On the
i1iO 2 it went straight home from most places, but by a detour from two parts
of the bed, and we found those late. Here **i1Profiler itself puts the arm
there**: you never push it.

For each place, lay **Sheet S-cut** there and:

1. Type `r` (after the first), start the take, type the label with its letter.
2. Start a measurement of Sheet S-cut in **patch by patch** mode, aim as
   i1Profiler asks.
3. Let it read the first two or three patches. **While the arm stands still on
   a patch** (between two moves), first type `d` if the measuring head is down
   on the sheet at that moment, or `u` if it is up, then force-quit i1Profiler
   (`killed`). In patch by patch mode the head is probably down on the sheet
   when i1Profiler goes away, and may stay down until i1Profiler starts again.
   That is expected; at worst it leaves a mark on the sheet, not on the table.
4. Note where the arm stands. Wait 20 seconds.
5. Start i1Profiler again. Note **exactly** the way the arm takes home:
   straight, or first to somewhere else (where?), then home.
6. Quit i1Profiler normally (`quit`). End the take.

The places (as you stand in front of the table):

- **a**: the back left;
- **b**: the back right;
- **c**: the front left;
- **d**: the front right;
- **e**: the middle, close to the arm's resting place;
- **f**: the free arm beside the calibration reference: as in B08, go on
  until i1Profiler asks you to aim, force-quit it, and **only if the arm moves
  as freely as when you aim**, move it gently to the strip beside the white
  calibration reference (or wherever B04 calibrated), as far to the side as it
  goes without force. Then go on from step 4.
- **g**: beside the calibration reference, put there by i1Profiler itself:
  start a measurement and, **while i1Profiler calibrates** (the arm then stands
  at the calibration reference without anyone moving it), type `calibrating`,
  then force-quit i1Profiler (`killed`). Then go on from step 4. No sheet is
  needed for this one.

If a place cannot be reached because the sheet will not lie there, note that
and go on.

### B14. Switched off and on while i1Profiler runs (optional, about 10 min)

**Labels:** `IO3-B14a` (idle), `IO3-B14b` (during aiming). **This tells us**
what i1Profiler does when the table disappears and comes back while it is
running.

**a. Idle:**

1. Start the take, type `IO3-B14a`. Start i1Profiler and let it find the
   table.
2. Switch the table off (`power off`). Wait 10 seconds. Note what i1Profiler
   says.
3. Switch it on (`power on`). Note what i1Profiler does (does it find the
   table again by itself?).
4. Quit i1Profiler. End the take.

**b. During aiming:**

1. `r`, start the take, type `IO3-B14b`. Start a measurement of Sheet S and go
   on until it asks you to aim.
2. Switch the table off (`power off`). Wait 10 seconds. Switch it on (`power on`).
3. Note what i1Profiler says. If it can go on, follow it; if not, cancel or
   quit.
4. If you quit it, start i1Profiler again and note what the arm does. Quit
   it. End the take.

### B15. The USB cable pulled during a measurement (optional, about 10 min)

**Label:** `IO3-B15`. **This tells us** what the table does when the computer
disappears in the middle of a movement, and how i1Profiler takes it up again.
(The head may stay down on the sheet for a moment; that can mark a sheet, not
the table.)

1. Start the take, type the label.
2. Start a measurement of Sheet S (scanning mode), aim, and let the first row
   start.
3. During the **second** row, pull the table's USB cable out of the computer.
   Type `pulled`.
4. Note what the arm does. Wait 30 seconds. Note what i1Profiler says.
5. Plug the cable in again (`plugged`). Note what i1Profiler does.
6. If the arm does not come to rest by itself within a minute, switch the
   table off and on.
7. Start or restart i1Profiler, let it find the table, quit it. End the take.

**End of Part 2.** Type `q` and end the run. On a Mac, at the end of the
sitting, switch SIP back on.

---

## 12. Only if you are comfortable with it

**OPTIONAL EXTRAS. About 15 minutes. Skip any of them if you are in any doubt:
we can work without them.** These are things done by hand on the table that
i1Profiler does not ask for. The recording tool's own README leaves them out
of its steps on purpose, because nobody can promise they are harmless for the
table. They are here because only a real table can answer them, and you
decide. They are **not** normal use.

What we know from the first table: while it was switched on, its motors held
the arm. An idle, switched-on table even pulled an arm that was pushed away
from its resting place back home by itself: the arm resisted, and returned.
**Never push against a motor that holds.**

Do them in a run of their own, or as further takes at the end of Part 2.

### X1. The arm pushed while the table is on and idle

**Label:** `IO3-X1`. **This tells us** whether the i1iO 3 holds its arm and
pulls it back, and whether that shows on the USB cable.

1. i1Profiler closed, the table on, the arm at rest. Start the take, type the
   label.
2. Touch the arm very lightly in the direction away from its resting place.
   **If it does not move at the lightest touch, stop here**, note "held", and
   end the take.
3. If it moves freely: move it about 5 cm and let go. Note whether it goes
   back by itself. Wait 30 seconds.
4. Start i1Profiler, note what the arm does, quit it. End the take.

### X2. Switched on with the arm out

**Label:** `IO3-X2`. **This tells us** what the table's own start-up does when
the arm was not at rest at power-on (on the first table, the start-up brought
it home).

1. Start the take, type the label. Switch the table **off** (`power off`).
2. Touch the arm lightly. **Only if it slides freely with the power off**,
   move it about 10 cm out over the bed. Otherwise switch on again, note
   "does not slide", and end the take.
3. Switch the table **on** (`power on`). Keep your hands away. Note what the
   arm does by itself.
4. Start i1Profiler, note what the arm does, quit it. End the take.

### X3. The instrument not in the arm

**Labels:** `IO3-X3a`, `IO3-X3b`. **This tells us** what i1Profiler and the
table say when the instrument is missing (X-Rite's software has its own
message for it).

On the i1iO 2 the instrument's cable plugged into a socket on the arm. When
the instrument is out, **lay it on the table next to the arm so that its cable
is slack**, never hanging or pulled.

**a. At the start:**

1. Start the take, type `IO3-X3a`. Switch the table off. Take the instrument
   out of the arm and lay it beside the arm, cable slack.
2. Switch the table on. Start i1Profiler. Note what it says and what the arm
   does. Try to start a measurement and note what i1Profiler says.
3. Quit i1Profiler. Switch the table off, put the instrument back, switch it
   on. End the take.

**b. While the arm waits for you to aim:**

1. `r`, start the take, type `IO3-X3b`. Start a measurement of Sheet S and go
   on until it asks you to aim.
2. **While the arm stands still**, take the instrument out of the arm and lay
   it beside it, cable slack. Note what i1Profiler says.
3. Put the instrument back, follow what i1Profiler asks, then cancel. End the
   take.

Never take the instrument out while the arm moves.

---

## 13. Part 3: the whole bed, the vendor's speed, the conditions

**IMPORTANT. One run (or two, split after B20), about 4.5 hours, of which one
hour is waiting. Sheets S-cut, F, R1 to R5, P, plain sheets.** This part makes
sure ChromIQ never needs another round for a place on the bed, a patch length,
a speed or a condition.

### B16. Aiming everywhere on the bed (about 25 min)

**Labels:** `IO3-B16a` to `IO3-B16f`, one take each. **This tells us** which
places the arm can reach (your aim points), the moves i1Profiler computes from
them, and how far beyond the aim points it runs for a row.

For each place: lay the sheet there, start a measurement in scanning mode, aim
as i1Profiler asks, let it read the **first row**, press **Cancel**
(`cancel`), and let the arm stop. Note where the sheet lay (a photo of the bed
is ideal).

- **a**: Sheet S-cut at the back left, as far back as it will lie;
- **b**: Sheet S-cut at the back right;
- **c**: Sheet S-cut at the front left (nearest you);
- **d**: Sheet S-cut at the front right;
- **e**: Sheet S-cut in the middle, turned by a few degrees (the angle of a
  sheet laid in a hurry);
- **f**: Sheet F (the full page) laid exactly as i1Profiler shows.

### B17. An aim point beyond the arm's reach (about 10 min)

**Label:** `IO3-B17`. **This tells us** how i1Profiler refuses a point the arm
cannot reach, and how far the arm can really go.

1. Lay the **plain sheet larger than the bed** (or Sheet F pushed as far
   towards one corner as it will go) so that one corner lies beyond where you
   think the arm can reach.
2. Start the take, type the label.
3. Start a measurement of Sheet F. When it asks you to aim, move the free arm
   **gently** towards the far corner, as far as it goes **without force**, and
   aim there. Note where it stopped.
4. Note exactly what i1Profiler says. If it refuses, follow its advice once.
   If it accepts, let it read the first row, then cancel. End the take.

### B18. Every patch length, and every speed setting (about 45 min)

**Labels:** `IO3-B18a` onwards, one take each. **This tells us** the speed
i1Profiler uses for each patch length, how far it runs before the first and
after the last patch, and the timing of the light against the move. On the
i1iO 2 the speed depended on the patch length, and the speeds we had not
recorded had to be asked for again.

For each try: start the take with its label, set up the measurement in
scanning mode with the sheet and setting named, aim, let it read **both
rows** to the end, save the measurement as the label, end the take. In the
one-line note: the patch size (as you noted it when you made the sheet), the
setting, and how long one row took.

- **a to e**: Sheets **R1, R2, R3, R4, R5** in turn, each at the **default**
  speed (`IO3-B18a` = R1 ... `IO3-B18e` = R5);
- **f**: Sheet R1 at the **fastest** speed setting i1Profiler offers (only if
  it offers a speed choice);
- **g**: Sheet R5 at the **fastest** speed setting;
- **h**: Sheet R3 at the **slowest** speed setting;
- **i onwards**: any other scanning setting i1Profiler offers for the table
  (an accuracy or averaging option, "measure twice"): Sheet R3, one take each,
  and note the name of each.

### B19. A row i1Profiler cannot read the first time (about 10 min)

**Label:** `IO3-B19`. **This tells us** what i1Profiler does with a row it
cannot read (on the i1iO 2: it read the row again more slowly, then patch by
patch, without asking), which speeds it uses for that, and what it says.

1. Lay Sheet S where you want it, and mark its three aim points lightly with
   a pencil on a **plain sheet** laid in the same place instead (or on the
   bed's edge, if you prefer not to mark the plain sheet).
2. Start the take, type the label.
3. Start a measurement of **Sheet S** in scanning mode and aim at the three
   pencil marks.
4. Let i1Profiler try the first row. Note everything it does: how many times
   it runs along the row, at what pace, whether it changes to patch by patch,
   what it says.
5. When it has given up or moved to the second row, press Cancel (`cancel`).
   End the take.

### B20. Two pages (about 15 min)

**Label:** `IO3-B20`. **This tells us** what happens between pages: where the
arm goes, what i1Profiler asks, and whether each page is aimed again.

1. Start the take, type the label.
2. Start a measurement of **Sheet P** in scanning mode. Lay page 1 as asked,
   aim, let it read the whole page.
3. Do what i1Profiler asks for page 2 (lay page 2, aim again if asked). Note
   where the arm is while you change the sheet.
4. Let it read page 2 to the end and go home (`home`). Save the measurement as
   `IO3-B20`. End the take.

### B21. Measurement conditions (about 30 min)

**Labels:** `IO3-B21a` onwards, one take each. **This tells us** how the
i1Pro 3 is asked to measure on the table for each condition. By hand, an
i1Pro 3 measures M0, M1 and M2 in one pass; on the table that is to be
confirmed (the i1Pro 2 on the first table needed a second pass).

For each condition i1Profiler offers for the table: start the take with its
label, set the condition, measure **Sheet S** in scanning mode, the whole
sheet, save it as the label, end the take. Note how i1Profiler names the
setting, and whether each row was read once or twice.

- **a**: M0; **b**: M1; **c**: M2;
- **d**: "dual scan" or "M0, M1 and M2 together", if i1Profiler offers such a
  setting for the table;
- **e**: M3 with the **polarisation filter**, only if you own it: fit it as
  X-Rite's manual says, and note what i1Profiler asks;
- **f**: if your instrument is an **i1Pro 3 Plus**, and i1Profiler offers a
  choice that depends on it (aperture, patch size): one take with each;
- **g**: Sheet S **patch by patch** with M1 or M2, the whole sheet.

### B22. The height and the sheet hold (about 10 min)

**Labels:** `IO3-B22a`, `IO3-B22b`. **This tells us** whether the height
setting and the sheet hold are commands over USB or only knobs and switches on
the table.

- **a, the height:** if your table has a height or thickness adjustment: with
  i1Profiler open and idle, start the take, set the height for a thick card
  (or the thickest it allows), then back to plain paper. Note how it is set (a
  knob, a lever, a spacer, a setting in i1Profiler). If i1Profiler has its own
  setting for the media thickness, change it there too and note its name.
  End the take.
- **b, the sheet hold:** with i1Profiler open and idle, start the take, switch
  the sheet hold on, wait 5 seconds, off, wait 5 seconds, on again. Note how it
  is switched (a button and its light, a setting in i1Profiler) and whether
  i1Profiler shows anything. End the take.

### B23. Errors provoked safely, Stop and Pause (about 15 min)

**Labels:** `IO3-B23a`, `IO3-B23b`. **This tells us** how i1Profiler and the
table report a problem, and what they do next.

- **a, no sheet:** start the take, start a measurement of Sheet S, aim, then,
  **while the arm stands still** waiting for your last aim point, take the
  sheet away and confirm the point. Let it try the first row. Note what it
  says. Cancel (`cancel`). End the take.
- **b, Stop or Pause:** if i1Profiler offers **Stop**, **Pause** or **Resume**
  during a measurement, start the take, and use each once during a row of
  Sheet S, typing its name each time and noting what the arm does. Then let it
  finish or cancel. End the take.

Never put your hand in the arm's way to stop it.

### B24. The reference sheet, read twice (about 25 min)

**Labels:** `IO3-B24a`, `IO3-B24b`. **This tells us** i1Profiler's own values
for one sheet, read both ways, so that ChromIQ's readings of the very same
sheet can later be compared patch by patch with them.

1. Lay the **clean copy of Sheet F** (the reference sheet) in the middle.
2. **a:** in scanning mode, M0, default speed, read the whole sheet. Save as
   `IO3-B24a` in both forms.
3. **b:** without moving the sheet, read it **patch by patch**, the whole
   sheet. Save as `IO3-B24b` in both forms.
4. Keep this sheet flat, dry and out of the light afterwards. If ChromIQ ever
   drives your table, it is the sheet we will ask you to read again.

### B25. The long pause: idle for an hour, then measure again (about 75 min, 60 of them waiting)

**Labels:** `IO3-B25a`, `IO3-B25b`, `IO3-B25c` (and `IO3-B25d`). **This tells
us** whether i1Profiler talks to the table while nothing happens (keeping the
connection alive), what the instrument's light does when idle, and whether
i1Profiler asks for a new calibration after a long pause, and how it does a
second calibration in the same session. (ChromIQ's own rule, taken from
ArgyllCMS, is that a calibration lasts one hour. What i1Profiler does is what
this block finds out.) A good time for this block is just before a lunch
break.

1. **a:** start the take, start a measurement of Sheet S in scanning mode; if
   i1Profiler calibrates, let it (note that it did); read one row, cancel. End
   the take.
2. **b:** start the take and type `idle`. Now leave i1Profiler **open** and the
   table on, and touch nothing for **at least one hour**: no measurement, no
   calibration. Glance at the instrument's light once or twice and type what
   it does. After the hour, end the take.
3. **c:** start the take, start a measurement of Sheet S again. Note whether
   i1Profiler asks for a new calibration, and let it calibrate if it does.
   Aim, read one row, cancel. End the take.
4. **d (only if i1Profiler allows it):** a calibration on the **instrument's
   own** white reference, out of the table. Start the take, follow every step
   i1Profiler asks, note each. End the take.

**End of Part 3.** Type `q` and end the run.

---

## 14. Part 4: extras

**NICE TO HAVE. One run, about 30 minutes.**

### B26. The instrument by hand, out of the table (about 10 min)

**Label:** `IO3-B26`. **This tells us** which commands belong to the
instrument and which to the table, by comparing the same instrument by hand in
the same session.

1. Switch the table off. Take the instrument out of the arm.
2. Start the take, type the label.
3. In i1Profiler, measure by hand: calibrate as it asks, scan **one row** of
   Sheet S with the instrument's ruler, then read **one single patch** if
   i1Profiler offers spot reading by hand. Save as `IO3-B26`. End the take.
4. Put the instrument back in the arm.

### B27. A ChromIQ chart measured in i1Profiler (only with an i1Pro 3, not a Plus; about 15 min)

**Label:** `IO3-B27`. **This tells us** whether ChromIQ's chart for the i1iO
and its import of i1Profiler's result already work with your table, which
needs no driving at all.

**Who can do it:** only owners of an **i1Pro 3** (not a Plus). ChromIQ's
table chart is made for the i1iO 2 with an i1Pro 2, with patches smaller than
the 16 x 16 mm an i1Pro 3 Plus needs on the table. i1Profiler's release notes
say that i1iO 2 charts are read by the i1iO 3 **in patch by patch mode only**,
so choose that. Your table will not be in ChromIQ's list; choose the i1iO.

1. In ChromIQ, switch on Preferences > Beta > "X-Rite i1iO support" (restart
   ChromIQ as it asks), make a small chart for the i1iO in Create Chart, and
   print it.
2. Start the take, type the label. In i1Profiler, measure it with the
   function for a chart it did not make (for the i1iO 2 it is called "Measure
   Chart"), patch by patch: type the columns and rows ChromIQ shows beside its
   chart, aim at the three points ChromIQ marks. Save the result. End the take.
3. In ChromIQ, bring the file back with IMPORT in the Measure tab, and note
   what ChromIQ says.

### B28. The computer goes to sleep (optional, the very last block, about 5 min)

**Label:** `IO3-B28`. **This tells us** what happens to the connection when
the computer sleeps. On Windows a new USB address after sleep has made a
recording keep nothing before (the tool's change notes say this was likely, not proven), so do this one **last**.

1. Start the take, type the label. Start i1Profiler and let it find the table.
2. Put the computer to sleep. Wait one minute. Wake it.
3. Note what i1Profiler says. Start a measurement, aim, read one row, cancel.
4. Quit i1Profiler. End the take.

**End of Part 4.** Type `q`, end the run, and on a Mac switch SIP back on and
check it with `csrutil status`.

---

## 15. After the blocks: photos, files, a few questions

### Photos (a phone is fine)

1. The whole table from above, with the arm at its resting place.
2. The bed's markings (the corner marks, any scale) with **a ruler lying in
   the picture**.
3. The white calibration reference (or the place where the arm calibrates),
   from above and from the side, with the ruler.
4. The arm and the instrument's holder, from the side, and where the
   instrument's cable plugs in.
5. The height or thickness adjustment, and the sheet hold button, if there
   are any.
6. i1Profiler's settings pages for the table (screenshots): scanning and spot
   mode, speeds, patch sizes, conditions, page sizes.

**Please do not photograph the labels with serial numbers**, or cover them
before you take the picture.

### A few questions (answer in `notes.txt`; skip what you do not know)

1. Your table's model as printed on it (for example "i1iO 3" or "i1iO for
   i1Pro 3 Plus"), but not its serial number.
2. Your instrument: i1Pro 3 or i1Pro 3 Plus? Do you own the polarisation
   filter? Any transmission accessory for the table?
3. The i1Profiler version, and your computer's system and version.
4. Which patch sizes and page sizes i1Profiler offered for scanning and for
   patch by patch.
5. How the sheet hold is switched (a button, i1Profiler), if there is one.
6. How the head height is set, down to which thickness, up to which.
7. When something goes wrong, what does the table show (a light, a sound)?
8. Anything that surprised you.

## 16. What to send, and how

**Before you send anything, please look at it.** Everything is in your
`i1iO3-recordings` folder.

1. **One set per run:** on a Mac the `SEND-THIS-<date>.zip` the tool made; on
   Windows the **cleaned copy** of your Wireshark recording (below) and the
   tool's report (`chromiq-io-probe-<date>.txt`). **Never a full recording**:
   not the Wireshark file itself, not a Mac's `-full.pcap` files, not a folder
   whose name ends in `-FULL-do-not-send`. They can hold everything else on
   those USB connections, possibly even what you typed.
2. **`notes.txt`.**
3. **The saved measurements and the saved charts** (i1Profiler's files and the
   CGATS exports), named after their blocks.
4. **The photos and screenshots.**

**Where:** please open a
[new issue](https://github.com/itsab1989/ChromIQ/issues/new) in the ChromIQ
repository titled "Recordings: X-Rite i1iO 3", and attach the files there (a
zip of the whole folder is fine). This wins over the tool's own text, which
names the i1iO 2's issue. That issue,
[#129](https://github.com/itsab1989/ChromIQ/issues/129), shows how this went
for the first table.

**An issue is public.** The recordings contain your devices' serial numbers
and calibration data (section 3). If you would rather not post them publicly,
say so in the issue without attaching them, and we will agree a private way;
the tool's README describes one. Please do not send anything by private mail
unless you prefer it.

### On Windows: the cleaned copy, in four steps

1. Put `chromiq-io-probe-windows.exe` into your `i1iO3-recordings` folder,
   next to the saved Wireshark files.
2. Open that folder in File Explorer, click into the address bar at the top,
   type `cmd` and press Enter. A black command window opens in that folder.
3. Type this, with your file's name, and press Enter:

   ```
   chromiq-io-probe-windows.exe --clean run1-part1.pcapng
   ```

4. It says how many records it kept and what it removed, and ends with a line
   "the cleaned copy:" naming a new file, `run1-part1-cleaned.pcap`, next to
   the original. **Send that file**, never the original. Repeat for each run.

To be honest: `--clean` was made for recordings of handheld instruments, and
it has not been tried yet on a Windows recording of an i1iO 3. If it says it
kept nothing, or writes no cleaned copy, please say so in the issue, keep the
original, and we will find another way. If we find that a copy lacks the
table after a power cycle or a pulled cable, we will ask you for the original
**privately**, never in the issue.

## 17. What a recording cannot tell us, and what happens next

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
4. **If ChromIQ ever drives your table, its first run will be step by step,
   with your hands away**, as it was for the i1iO 2: ChromIQ explains each
   step before it moves, waits for your "yes", and keeps the power switch as
   the stop. Only what has worked once on your table then runs at full speed.

Nothing in this plan is a promise that ChromIQ will support the i1iO 3. Your
recordings are what makes it possible at all. Thank you.

---

## 18. The one-page checklist

One take per block: `Enter`, the label, the block, `e`, one line, then `r` for
the next (`q` after the last of a run). One line in `notes.txt` after each,
with the time to the second.

| done | block | label | priority | about |
|---|---|---|---|---|
| [ ] | getting ready: sheets printed, tool and Wireshark ready, SIP off (Mac) | | | 45 to 60 min |
| [ ] | B01 the table idle | `IO3-B01` | ESSENTIAL | 5 min |
| [ ] | B02 start and quit i1Profiler | `IO3-B02` | ESSENTIAL | 5 min |
| [ ] | B03 cold start | `IO3-B03` | ESSENTIAL | 5 min |
| [ ] | B04 calibration | `IO3-B04` | ESSENTIAL | 5 min |
| [ ] | B05 Sheet S in rows, to the end (saved) | `IO3-B05` | ESSENTIAL | 15 min |
| [ ] | B06 Sheet S patch by patch, to the end (saved) | `IO3-B06` | ESSENTIAL | 15 min |
| [ ] | B07 cancel mid-row, then quit | `IO3-B07` | ESSENTIAL | 10 min |
| [ ] | B08 a, b force-quit while aiming, then start again | `IO3-B08a`, `IO3-B08b` | ESSENTIAL | 12 min |
| [ ] | B09 force-quit during a row, then start again | `IO3-B09` | ESSENTIAL | 10 min |
| [ ] | *end run 1 (Part 1, about 1.5 h with the notes)* | | | |
| [ ] | B10 quit normally while aiming | `IO3-B10` | ESSENTIAL | 6 min |
| [ ] | B11 quit normally with the arm out | `IO3-B11` | ESSENTIAL | 6 min |
| [ ] | B12 the aiming mode across a power cycle | `IO3-B12` | ESSENTIAL | 10 min |
| [ ] | B13 a to g, the way home from every part of the bed | `IO3-B13a` ... `IO3-B13g` | ESSENTIAL | 35 min |
| [ ] | B14 a, b switched off and on while i1Profiler runs (optional) | `IO3-B14a`, `IO3-B14b` | ESSENTIAL (optional) | 10 min |
| [ ] | B15 USB cable pulled (optional) | `IO3-B15` | ESSENTIAL (optional) | 10 min |
| [ ] | *end run 2 (Part 2, about 1.5 h)* | | | |
| [ ] | X1 the arm pushed, table on (only if comfortable) | `IO3-X1` | OPTIONAL EXTRA | 5 min |
| [ ] | X2 switched on with the arm out (only if comfortable) | `IO3-X2` | OPTIONAL EXTRA | 5 min |
| [ ] | X3 a, b the instrument not in the arm (only if comfortable) | `IO3-X3a`, `IO3-X3b` | OPTIONAL EXTRA | 8 min |
| [ ] | B16 a to f, aiming everywhere | `IO3-B16a` ... `IO3-B16f` | IMPORTANT | 25 min |
| [ ] | B17 an aim point beyond reach | `IO3-B17` | IMPORTANT | 10 min |
| [ ] | B18 a onwards, every patch length and speed (saved) | `IO3-B18a` ... | IMPORTANT | 45 min |
| [ ] | B19 a row that cannot be read | `IO3-B19` | IMPORTANT | 10 min |
| [ ] | B20 two pages (saved) | `IO3-B20` | IMPORTANT | 15 min |
| [ ] | B21 a to g, conditions (saved) | `IO3-B21a` ... `IO3-B21g` | IMPORTANT | 30 min |
| [ ] | B22 a, b height, sheet hold | `IO3-B22a`, `IO3-B22b` | IMPORTANT | 10 min |
| [ ] | B23 a, b errors, Stop and Pause | `IO3-B23a`, `IO3-B23b` | IMPORTANT | 15 min |
| [ ] | B24 a, b the reference sheet (saved) | `IO3-B24a`, `IO3-B24b` | IMPORTANT | 25 min |
| [ ] | B25 a to c (d), the long pause | `IO3-B25a` ... `IO3-B25d` | IMPORTANT | 75 min |
| [ ] | *end run 3 (Part 3, about 4.5 h)* | | | |
| [ ] | B26 the instrument by hand (saved) | `IO3-B26` | NICE TO HAVE | 10 min |
| [ ] | B27 a ChromIQ chart in i1Profiler (i1Pro 3 only) | `IO3-B27` | NICE TO HAVE | 15 min |
| [ ] | B28 computer sleep (optional, last) | `IO3-B28` | NICE TO HAVE | 5 min |
| [ ] | *end run 4 (Part 4, about 30 min); Mac: SIP on, `csrutil status`* | | | |
| [ ] | photos, screenshots, questions | | | 15 min |
| [ ] | Windows: a cleaned copy of each run (section 16) | | | 10 min |
| [ ] | looked at every file, then sent (section 16) | | | |

**The one-afternoon route:** getting ready, B01 to B13, end of the run; about
3 to 3.5 hours.

**Privacy, once more:** recordings hold your devices' serial numbers and
calibration data; an issue is public; never send a full recording; on a Mac,
switch SIP back on at the end of every sitting.

---

## Appendix A: why each block is there

Every block answers something the first table we supported (an i1iO 2 with an
i1Pro 2) either taught us from a recording, or made us ask for again later.
"Later" always meant another release and another round with its owners.

| block | what the first table taught us | what ChromIQ needs it for |
|---|---|---|
| B01, B02 | Its identity answers and opening lines were exact and fixed; a second model must be recognised by its own before anything is sent. | Telling the i1iO 3 apart, and deciding whether the i1iO 2's code can be reused. |
| B03 | A just-switched-on table reported a state of its own and needed a start-up of its own. | The cold start, without i1Profiler. |
| B04, B25 | Where to calibrate (the table's reference against the instrument's own) was an open question until a later recording and a comparison of both. When i1Profiler calibrates again was never recorded; ChromIQ uses ArgyllCMS's one-hour rule. | The calibration step, and when to repeat it. |
| B05 | The normal scan of a row was missing from the first recordings (every row there had fallen back); the aiming geometry was settled only from a later round. | Aiming, rows as strips, the end of a job. |
| B06 | Patch by patch: the move, the reading and the pace per patch. | Patch by patch reading at i1Profiler's pace. |
| B07 | i1Profiler's cancel sends a different ending from the normal end of a job; it was recorded only later. | Every ending leaves a table the next start can take. |
| B08, B09 | A table that a program left without tidying up (ChromIQ's own untidy endings did it) kept its aiming mode, and ChromIQ's next start refused it. Only a recording of i1Profiler starting on such a table showed how to repair it. A free arm in that mode homed at a start is still unproven. | Recovering every untidy ending without i1Profiler. |
| B10, B11 | Every normal quit of i1Profiler that was recorded happened with the arm at rest, and it put the table back in order; a normal quit from the middle of aiming or with the arm out was never recorded. | The tidy-up ChromIQ copies for its own endings. |
| B12 | The aiming mode was seen to survive a power cycle, but never confirmed. | Telling the person truthfully what the power switch resets. |
| B13 | i1Profiler homed straight from most places, but by a detour from two parts of the bed (one beside the calibration reference); both were found late, and early versions refused places no recording had covered. | Going home from every part of the bed, the way the vendor does. |
| B14, B15 | A lost link with a move still waiting needed the power switch; what the table does after the cable comes back was never recorded. | The lost-link page, and the way back. |
| X1, X2 | An idle, switched-on table pulled a pushed arm back by itself; a table switched on with the arm out brought it home in its start-up. | What to tell the person, and the start-up from any arm position. |
| X3 | Not recorded on the first table. | The page for a missing instrument. |
| B16, B17 | Places the arm had never been in a recording were at first fenced off, although the person could aim there; removing those fences took several correction rounds. The true end of travel is still not recorded on any side. | One reach rule from the start, with no fence that has no physical reason. |
| B18 | The row speed depended on the patch length; with only some lengths recorded, ChromIQ first read rows more slowly than i1Profiler. The run beyond the end patches and the timing of the light against the move set the shortest patch. | Rows at the vendor's speed for every patch length, and placing the readings on the patches. |
| B19 | i1Profiler re-reads a failed row more slowly and then patch by patch, asking nobody; the slower speeds were recorded for some rows only. | Reading a failed row again as the vendor does. |
| B20 | The page change: where the arm waits, and that each page is aimed again. | Several pages in one measurement. |
| B21 | On the i1Pro 2, M1 and M2 needed a second pass with its own speed on the table. The i1Pro 3 measures them in one pass by hand; on the table that is to be confirmed. | The measurement conditions on the table. |
| B22 | The height and the sheet hold were never recorded; ChromIQ's texts only remind the person of them. | Knowing whether they are commands at all. |
| B23 | X-Rite's software has its own messages for a missing sheet and an interrupted move; none was recorded. | Truthful pages for each fault. |
| B24 | A reading in a recording can only be checked against the program's own saved result of the same measurement; that pairing settled which white reference to use. | Comparing ChromIQ's readings with i1Profiler's on the same sheet. |
| B25 | Idle traffic was not recorded on the first table. | Whether ChromIQ must keep the connection alive, and when to calibrate again. |
| B26 | The table and the instrument were separate USB devices on the first table, meeting only in time. | Separating the table's commands from the instrument's. |
| B27 | The chart-out, measurement-back route worked long before the drive did. | Both routes at the same time. |
| B28 | A new USB address after sleep made a recording keep nothing. | Whether a sleeping computer breaks the connection. |

## Appendix B: what we assume about the i1iO 3

**Everything here is to be confirmed by the first recording.** Some of it comes
from X-Rite's own documents, some from retailers quoting X-Rite, and some is a
guess from the i1iO 2.

**From X-Rite's own documents** (the i1iO 3 quick start guide and the driver
files that come with i1Profiler, read in an earlier study; still to be checked
on a real table):

- The media area is 320 x 230 mm, up to 10 mm thick. That is X-Rite's media
  figure, not a measured reach of the arm.
- An electrostatic mat holds the sheet, switched with a button that has a
  green light.
- The table has an integrated calibration reference.
- The smallest patch is 6 x 7 mm with an i1Pro 3 and 16 x 16 mm with an
  i1Pro 3 Plus.
- The same three-point aiming as on the earlier tables, confirmed with the
  instrument's button.
- X-Rite's driver files name the USB ID 0765:30B0 for the i1iO 3 (the
  recording tool uses that name). The i1iO 2 is 0971:2004, a USB-to-serial
  chip speaking short lines of text, and the i1Pro 3 is 0765:6009, a separate
  USB device. Whether the i1iO 3 is one USB device or two, and whether it
  speaks the same kind of lines, is the first thing the tool's report (B01)
  and B02 will show.
- i1Profiler's release notes say that i1iO 2 charts are read by the i1iO 3 in
  patch by patch mode only, so the i1iO 3's own charts for scanning differ in
  some way we do not know.

**Published, quoted by retailers, not checked by us:** 14 x 14 mm as the
smallest patch patch by patch with an i1Pro 3 Plus; 16 x 20 mm for M3; up to
33 mm media thickness with an optional spacer; the i1Pro 3 Plus's 8 mm
aperture (X-Rite, published).

**From our own work with the instruments:** by hand, an i1Pro 3 measures M0,
M1 and M2 in one pass and reads its ruler on a separate channel, and
i1Profiler drives its lights itself. How it is triggered on the table is not
known.

**From X-Rite's support note:** the i1Pro 3 and the i1iO 3 work with current
Windows 11 releases, unlike the i1Pro 2 and i1iO 2, which the newest
i1Profiler no longer supports.

**Guesses, to be dropped or confirmed:** that the i1iO 3 has a resting place,
an aiming mode and an end-of-job tidy-up like the i1iO 2's; that its arm is
held by its motors while it is on; that its power switch stops the arm at once.
