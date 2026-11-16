# ChromIQ i1iO session test program 0.5.0 (one step at a time; part C reads)

**This is an unofficial test program. It is not from X-Rite, and X-Rite has
nothing to do with it.** Running it is entirely your choice, at every single
step, without any warranty. Keep your hands and everything else away from the
arm while it moves, keep the table empty except for the chart or sheet a stage
asks for, and keep its power switch within reach.

This is the next test program for the **X-Rite i1iO 2** scanning table with an
**i1Pro 2**, written for ChromIQ issue #129 from the USB recordings you made
with i1Profiler. After opening the table it asks you to choose **one of three
parts** for this run (to run another part, start the program again):

* **Part A** is version 0.3.1, exactly as it was: the homing, three drives out
  over the empty table and back, the hand-alignment mode at the resting place,
  and the close. It sends the same bytes in the same order as 0.3.1. If you
  have not run 0.3.1 yet, run part A first: you can use this program instead
  of 0.3.1.
* **Part B** is new: i1Profiler's recorded spot measurement of row 1 from 14
  November (your session 3), over the **empty** table and **without
  measuring**. It is offered only after you confirm that part A (or 0.3.1) went
  well.
* **Part C** is new in 0.5.0: ChromIQ **reads** with the i1Pro 2 on the table,
  through its own reader (in the `bin` folder of this package): spot readings,
  a strip reading as i1Profiler does it, and your own printed ChromIQ i1iO
  sheet. You choose its stages one at a time. It is offered only after you
  confirm that parts A and B went well (in this version, or in 0.3.1 and
  0.4.0). See "Part C" below.

**0.5.0 contains everything 0.4.0 has**: parts A and B are unchanged on the
wire (we compared every simulated session of both versions byte for byte). So
you need only this download, whether or not you ran 0.4.0.

Before each step it tells you what will move, how far, how long it took when
i1Profiler did it, what is exactly as recorded and what goes one step beyond a
recording. You type `yes` to run it, or `skip`/`end`. After each step it asks
what you saw, heard and felt.

**Parts A and B never measure and never talk to the i1Pro 2. No part writes
anything into the table's memory or the instrument's memory, and no part sends
a line of its own for the measuring head.** The program is not part of the
ChromIQ app and does not need it.

## What is new in 0.5.0

* Part C, twelve stages that you choose one at a time from a menu: open and
  calibrate the instrument, spot readings at the resting place and on the
  recorded row, the recorded strip reading of 14 November replayed, your own
  ChromIQ sheet aimed at its three marks, a first computed move, a row and a
  whole page in spot readings, a row and a whole page as strip readings, and
  the homing. Each is explained first and needs your `yes`.
* **A stage that fails cleanly does not end the sitting.** "Cleanly" means:
  nothing is left waiting, and the arm read where it stands (or never moved).
  The program says what failed, keeps everything about it, and offers the next
  stage that does not depend on it. You can repeat a stage (each has its own
  limit). Anything not clean (a movement whose end is not known, a strip move
  that may still be waiting, a reading in the wrong place, Ctrl-C) ends the
  sitting for good, as in parts A and B.
* ChromIQ's own reader, `bin/chromiq-chartread`, comes with this package. It
  is the same reader ChromIQ uses when you measure by hand (ArgyllCMS 3.5.0
  inside), with the strip-reading mode for the table added. It never writes
  into the instrument's memory.
* Everything comes back in **one results zip** beside the log.
* The end texts in all parts now say only what the last position reading
  shows ("held when last checked", "at its resting place" only when the arm
  read there).


## What is new in 0.4.0

* The choice of part A or part B at the start. Part A is unchanged on the wire:
  we captured every 0.3.1 session from the 0.3.1 program and from this one in
  the simulator, and the bytes are identical.
* Part B, six steps: the drive to the place where i1Profiler starts every
  alignment, the hand-alignment mode there, you push the free arm by hand to
  the front right, the motors take it and drive it to the first patch, the 27
  recorded patch moves along row 1, and i1Profiler's homing and end of job.
* 29 more recorded lines: i1Profiler's short move to the alignment start (m1)
  and the 28 patch moves of your recorded row, each byte for byte, with the
  recorded target and the recorded speed. Nothing else is new on the wire.
* Two optional steps in part B: after you stop on row 1, a homing from the
  patch where the arm stands; and after the end of the job, the close (not
  recommended, see below).
* Questions during part B about the glider ring and the measuring opening:
  whether the ring stays on the mat all the time, and whether anything lifts or
  lowers. We believe there is no head-lowering command at all; what you see
  settles it.

## What changed since 0.3.0

* You ran 0.3.0 twice, and both times it stopped before the first homing,
  with nothing moved: the arm read X 1104, Y 110 and X 1101, Y 97, outside the
  range 0.3.0 allowed (X 1101 to 1103, Y up to 80). That was our fault, not
  your table's. Our own question before the opening asked you to push the
  free arm gently towards the front of the table, and that push moved it out
  by several millimetres; the touches after each stop
  probably pushed it further (we did not measure that). That
  question is gone: 0.3.1 never asks you to touch the arm before the first
  homing, and never after a stop.
* The touch questions that remain come only after a homing has brought the
  arm to its resting place, and they ask you to wiggle the holder gently from
  side to side, never to push it towards the front.
* The first homing of each step is now sent from a wider range: X 1090 to
  1115, Y up to 250 (25 mm). This goes one step beyond your recordings:
  i1Profiler sent this homing only from X 1102, Y 0 to 47, but it drove the
  arm along this same line under motor out to Y 250, and it homed from places
  much farther out. The one place where i1Profiler drove the arm out first
  instead of homing (X 1058, Y 317) stays outside the range. From 25 mm out
  the homing should take about 1.2 s; the program stops if it takes longer
  than 2 s.
* If the arm stands outside even this range, nothing moves, and the program
  tells you what is known to bring it back: open i1Profiler once, let it
  start the table, quit it, and run this program again without touching the
  arm.

## What changed since 0.2.1

* The range we used to check the arm's resting position was wrong twice. The
  arm's reading creeps slowly away from Y 0 the longer it stands, so we no
  longer guess a range from what we have seen. The homing is sent from the
  places i1Profiler sent it from (X 1102, Y 0 to 47), and, one small step
  further, from a wider range on the same line (see above): that line is
  driven by i1Profiler's own moves out from the resting place in your
  recordings.
* New: three drives out over the empty table and back home, using only moves
  i1Profiler made on your table, with the same targets and the same speed.
* New: the hand-alignment mode, in which the arm is free, at the resting place.
  This step shows whether that mode lets the arm go. If you run this
  step, please also run the close afterwards: it is what switches the
  hand-alignment mode off again.
* The busy-table help and the "the table was not closed" note from the
  never-offered 0.2.2 are included.

## Part A: the steps of 0.3.1

The opening comes first, always, and only reads (11 lines, nothing moves). If
the table has just been switched on, the program stops after the sixth line
and asks you to let i1Profiler start the table first.

### Step 1: Send the arm to its resting place once

The arm is sent to its resting place, where it already is or nearly is: usually it moves a few millimetres, for about a third of a second, and at most 25 mm, for about a second. This is what i1Profiler does right after it opens the table.

*Not exactly as recorded:* i1Profiler sent this homing only from X 1102, Y 0 to 47; this program also sends it from X 1090 to 1115 and Y up to 250 (up to 25 mm out, about 1 mm to either side of the home line), the stretch i1Profiler drove the arm along under motor in your recordings. From 25 mm out it should take about 1.2 s; it is stopped if it takes longer than 2 s. If the arm stands even farther out, nothing moves.

4 lines, 1 movement. Our risk rating: **low**.

### Step 2: Drive out about 15 cm along i1Profiler's way to an alignment, and back home

After a homing, the arm drives out from its resting place 25 mm straight ahead, then on to a point 10 mm to the side and 150 mm out (table position X 1000, Y 1500), in about 0.7 s and 1.6 s, exactly the two moves i1Profiler makes before it asks you to align a chart. The program checks that the arm arrived, then sends it home (about 2 to 4 seconds), checks that it is at rest and sends it home once more, as i1Profiler does.

*Not exactly as recorded:* In the recordings these two moves always came 7.5 s after an i1Pro 2 calibration on the tile; here they come right after the homing, and the program asks where the arm is between them (i1Profiler sent them back to back) so that it stops if the first did not arrive. i1Profiler never sent the arm home from exactly this point. With the motors holding the arm, the closest recorded homing nearer home started at X 1102, Y 1202 (about 3 cm from this point); the nearest one of all started at X 1172, Y 1663 (about 2.4 cm away, farther out). The other recorded homings with the arm held started farther out.

21 lines, 5 movements. Our risk rating: **medium**.

### Step 3: Drive straight out about 15 cm and back home

After a homing, the arm drives straight out from its resting place by 150 mm (table position X 1102, Y 1498) in about 1.7 s: the first move i1Profiler made at the start of the seven measuring sessions in your recordings that began without a calibration (after a calibration it used the way out of step 2). The program checks that it arrived and sends it home (about 2 to 3 seconds), then checks it at rest and sends it home once more.

*Not exactly as recorded:* i1Profiler followed this move with a second move, never with a homing. With the motors holding the arm, the closest recorded homing nearer home started at X 1102, Y 1202, on this same line about 3 cm nearer home; the nearest one of all started at X 1172, Y 1663 (about 1.8 cm away, farther out).

19 lines, 4 movements. Our risk rating: **medium**.

### Step 4: Drive out 15 cm, across 14 cm to the far side, back, and home

After a homing, the arm drives straight out by 150 mm (about 1.7 s), then sideways by 140 mm to table position X 2507, Y 1498 (about 1.7 s), exactly the two moves i1Profiler made at the start of the seven measuring sessions in your recordings that began without a calibration. The program checks that it arrived, drives it back the same way to X 1102, Y 1498, checks again, and sends it home (about 2 to 3 seconds), then checks it at rest and homes once more.

*Not exactly as recorded:* The way back to X 1102, Y 1498 is the recorded sideways move driven backwards (its target is recorded, its start is not); i1Profiler went on from the far side to the alignment instead. The program also asks where the arm is between the first two moves (i1Profiler sent them back to back), so that it stops if the first did not arrive.

27 lines, 6 movements. Our risk rating: **medium**.

### Step 5: Let the arm go (the mode i1Profiler uses for aligning a chart) and take it back

With the arm at its resting place, the program switches on the hand-alignment mode, exactly the lines i1Profiler sends before it asks you to push the arm over your chart (f3, then f1). The arm should then move freely. You touch it gently once, without moving it away from the tile. Then the program takes it back the way i1Profiler does when you cancel an alignment: it sends the arm home (the motors take it again) and homes once more. Afterwards only the close may follow, and we recommend it: the close is what switches the hand-alignment mode off again.

*Not exactly as recorded:* i1Profiler switched this mode on only out on the table, after a move to the alignment start; here it is switched on at the resting place. Taking the free arm back with a homing is recorded three times: twice it worked, from far out on the table (2.4 s and 4.0 s); once, when the homing was sent two milliseconds after a button on the instrument had been pressed, the table answered with status 3 instead. What status 3 means is not known. If the table answers that here, the program stops and sends nothing more; the table is then still in the hand-alignment mode, and the program tells you what to do.

25 lines, 3 movements. Our risk rating: **medium**.

### Step 6: Close the table the way i1Profiler does

The two lines with which i1Profiler closes the table. Nothing moves.

*Not exactly as recorded:* Nothing: this is i1Profiler's close after a homing and a pause, as recorded.

3 lines, 0 movements. Our risk rating: **low**.

At most **110 lines and 19 movements** in one session, and every step at
most its own lines and movements. Each step can be run once.

In part A the person is never asked anything while the arm is away from its resting
place: once a step starts, it runs until the arm is home again (or until
anything is not as expected, and then nothing more is sent).

## Part B: the recorded spot row, over the empty table

The opening comes first, as in part A. Each step of part B needs the one before
it, so inside part B there is no skipping: `end` ends part B there, and nothing
more is sent. In part B you are asked questions while the arm stands out on
the table, but never while it moves.

### B1: Send the arm to its resting place once

The same homing as step 1 of part A: the arm is sent to its resting place, where it already is or nearly is (usually a few millimetres, about a third of a second).

*Not exactly as recorded:* As in part A: i1Profiler sent this homing only from X 1102, Y 0 to 47; this program also sends it from X 1090 to 1115 and Y up to 250, and stops if it takes longer than 2 s. If the arm stands farther out, nothing moves.

At most 4 lines, 1 movement. Our risk rating: **low**.

### B2: Drive to the place where i1Profiler starts every alignment, and let the arm go there

The arm drives straight out from its resting place by 150 mm (about 1.7 s), then 140 mm sideways to the far side, towards the left as you see the table when you lay a chart on it (about 1.7 s), then makes one short move of a few centimetres (about 0.4 s) to the place where i1Profiler starts every chart alignment. These are exactly i1Profiler's three moves at the start of the five measuring sessions of 14 November. Then the program sends i1Profiler's lines that switch on the hand-alignment mode (f3, then f1): the motors should let the arm go. The program reads where the arm is and asks you to touch it gently once.

*Not exactly as recorded:* The short move (m1) is sent exactly as i1Profiler sent it, from the same place, but what it does is not fully understood: its time does not fit a normal move, and we believe it puts the alignment sight (the cross hairs), not the measuring opening, on the alignment start. i1Profiler never read the position right after it; this program does, between the moves and after m1, and stops if the arm is not where one of the two explanations puts it. In the recordings these moves followed i1Profiler's end of the previous job; here they follow this program's homing.

At most 19 lines, 3 movements. Our risk rating: **medium**.

### B3: You push the free arm by hand to the front right of the table

Nothing moves under motor in this step. You push the free arm gently by the instrument holder, as you do in i1Profiler's alignment, to the place where the first patch move of your recorded spot measurement started: in the front right part of the table, about 24 cm to the right of the resting place and about 27 cm towards the front (where the alignment sight was over the bottom-right corner patch of your chart on 14 November). Then you take your hands off and type placed, and the program reads where the arm is. The place is a small box, 16 mm wide and 10 mm deep, so the program tells you how far to push it if it is not there yet; you have 6 tries.

*Not exactly as recorded:* i1Profiler sent these lines (s0, f4 four times) after you had aimed at the third corner patch with the instrument's button and the position under the sight had been read (p1); here nothing is aimed, there is no p1, and typing placed takes the place of the button. The position reads between your tries are not in the recordings (reads only; i1Profiler read the free arm twice right before its first patch move).

At most 11 lines, 0 movements. Our risk rating: **low**.

### B4: The motors take the arm and drive it to the first patch

With your hands off the arm, the program reads its position twice, exactly as i1Profiler does, and only if it is inside the box and has not moved, sends i1Profiler's first patch move: the motors take the free arm and drive it about 10 cm towards the back of the table (about 1.5 s) to the first patch of row 1 (table position X -1181, Y 1658). The program then checks that it arrived.

*Not exactly as recorded:* The line, its target and speed are exactly as recorded. Your recordings hold 10 chart alignments: in 2 of them, i1Profiler's next movement was a first patch move like this one, straight from the free arm; in 5, it first sent the line c4 and then a move (the scan measurements); in 3, it sent a homing. The start is where your hand left the arm, inside the box of the recorded starts but not exactly the recorded start (X -1297, Y 2681). After it, the arm is held by the motors again, but the table stays in the hand-alignment mode until step 6.

At most 4 lines, 1 movement. Our risk rating: **medium**.

### B5: Row 1, patch by patch, as i1Profiler measured it (without measuring)

The arm steps along row 1 to the left, 27 steps of about 8.7 mm, one step about every 1.4 seconds (each move takes about 0.43 s, then the program waits 1 s), about 40 seconds in all, 23.5 cm altogether, exactly the 27 moves of your recorded spot measurement. Before each step it reads where the arm is and stops if it is not within half a millimetre of the patch it was sent to. While it runs you can press Enter to stop at the next patch, or Ctrl-C (then it sends nothing more at all). Please watch the round measuring opening and the glider ring under it.

*Not exactly as recorded:* The moves are exactly as recorded. In the recording the instrument took two readings in each 1 s pause; here the instrument is not used, and the program only waits.

At most 54 lines, 27 movements. Our risk rating: **low-medium**.

### B6: Home from the row end and end the job the way i1Profiler does

The arm is sent home from the end of row 1 (about 2.6 s), then the program sends i1Profiler's end-of-job lines: f0 switches the hand-alignment mode off, f4 should then answer 00. Last, it reads that the arm is at its resting place.

*Not exactly as recorded:* Nothing in the lines or their order: this is i1Profiler's end of your recorded spot measurement, from the same place. The last position read is added (i1Profiler read it at the start of the next job).

At most 8 lines, 1 movement. Our risk rating: **low**.

### Optional steps of part B

**Send the arm home from the patch where you stopped, and end the job.** The arm is held by the motors at the patch of row 1 it reached last. This step sends it home from there (2.5 to 4 s) and then sends i1Profiler's end-of-job lines, which switch the hand-alignment mode off, exactly as at the end of the row. If you say no, nothing more is sent and the arm stays where it is.

*Not exactly as recorded:* i1Profiler sent this homing from two places on this same row with the arm held (X 1172, Y 1663 at the row end, 2.6 s; X -1088, Y 1636 near the row's other end, 3.7 s, after the previous job); every patch of row 1 lies on the line between them. From this very patch it was never sent.

8 lines, 1 movement. Our risk rating: **medium**.

**Close the table the way i1Profiler closes it when you quit.** The two lines with which i1Profiler closes the table when you quit it. Nothing moves.

*Not exactly as recorded:* i1Profiler sent this close only after a homing (i1, s0); here it would follow the end-of-job lines, which already contain f0, so f0 would come twice. That is not recorded.

3 lines, 0 movements. Our risk rating: **low**.

The homing from a patch is offered only when you stop on row 1 with Enter (or
type `end` before the row), never after Ctrl-C or after anything unexpected. The
close is offered after the end of the job; we do not recommend it, because the
end of the job already leaves the table as i1Profiler leaves it between jobs.

Part B sends at most **114 lines and 33 movements** in one session.

## Every line it can send

In parts A and B it can send only **45 different lines**. Each one is a line i1Profiler
itself sent to your table in your recordings, byte for byte. Part C adds five
more recorded lines and the computed moves; see "Part C" below. `BYTES.md` lists
each with the exact places in your recordings and its bytes. `python3
i1io_session.py --plan` prints every step and line; `--dry-run` adds every byte.

| Line | What it does (as far as we know) |
|---|---|
| `;a133` | asks who the table is (twice) |
| `;k228` | asks a fixed value |
| `;u8000060000100d1` | reads part 1 of the table's memory block (a read only; it holds the serial number, which is never written down) |
| `;u8000061000068c3` | reads part 2 of the memory block (a read only) |
| `;a034` | tells whether the table has just been switched on (111800) or is started (130000) |
| `;s022` | asks for the status |
| `;f42b` | asks a mode flag: 00 normally, 01 in the hand-alignment mode; it does not tell whether the motors hold the arm |
| `;p025` | asks where the arm is |
| `;i12b` | **moves**: sends the arm to its resting place |
| `;m0044e00fa012c0e` | **moves**: to X 1102, Y 250 (25 mm straight out), speed 300 |
| `;m003e805dc012c06` | **moves**: to X 1000, Y 1500, speed 300 |
| `;m0044e05da012c0b` | **moves**: to X 1102, Y 1498 (150 mm straight out), speed 300 |
| `;m009cb05da012cda` | **moves**: to X 2507, Y 1498 (140 mm to the side of that), speed 300 |
| `;f12e` | switches on the hand-alignment mode (the arm is let go) |
| `;f02f` | first closing line |
| `;f32c` | second closing line; i1Profiler also sends it right before the hand-alignment mode |
| `;m10b10055b012c42` | **moves** (part B): i1Profiler's short move to the place where every alignment starts; we believe it puts the alignment sight there, not the measuring opening |
| the 28 patch moves | **move** (part B): the arm to each patch of row 1 of your recorded spot measurement, speed 300: `;m0fb63067a012c03`, `;m0fbba067b012ca8`, `;m0fc11067b012c08`, `;m0fc68067b012cfc`, `;m0fcbf067b012ca2`, `;m0fd17067b012c01`, `;m0fd6e067c012ccd`, `;m0fdc5067c012cd0`, `;m0fe1c067c012cd3`, `;m0fe74067c012cfc`, `;m0fecb067c012ca2`, `;m0ff22067d012c01`, `;m0ff79067d012cf5`, `;m0ffd0067d012cd1`, `;m00027067d012c68`, `;m0007e067d012c35`, `;m000d5067d012c38`, `;m0012c067e012c3a`, `;m00184067e012c63`, `;m001db067e012c09`, `;m00232067e012c69`, `;m00289067e012c5d`, `;m002e0067f012c38`, `;m00338067f012c61`, `;m0038f067f012c2e`, `;m003e6067f012c31`, `;m0043d067f012c34`, `;m00495067f012c5d` |

**What it never sends:** the start-up of a table just switched on, the scanning
lines that only occur between "arm over a patch" and "reading" in a scan (one
of them was once thought to lower the head), the position read after the
instrument's button (p1), any write to any memory, any target the arm was not
driven to in your recordings, any other speed, and nothing at all to the
i1Pro 2.

## What could go wrong, and what to do (part A)

* **A move ends somewhere else, takes much longer or shorter than recorded, or
  an answer is late or strange:** the program sends nothing more at all. The
  arm stays where it is; please do not push it around. Then open i1Profiler
  once, let it start the table, and quit it. We expect i1Profiler to bring the
  arm home: it did so once in your recordings, from 3 cm out. If it does not
  bring the arm to its resting place, or shows a problem with the table,
  switch the table off, wait ten seconds, switch it on again, and open
  i1Profiler once more. That is a recovery for this case, not a routine step.
* **Anything looks or sounds wrong while the arm moves:** switch the table off
  at its power switch or pull its power plug. That is always allowed and is
  the emergency stop. Pulling the USB cable does not stop a movement: the table
  has its own power supply.
* **The table never reports that a movement finished:** keep your hands away,
  switch the table off, wait ten seconds, switch it on again, then open
  i1Profiler once and quit it.
* **You stop inside the hand-alignment step** (Ctrl-C at the touch question),
  **the table does not take the arm back** (it answered status 3 once in your
  recordings; what that means is not known), **or the session ends after that
  step without the close:** the table is still in the hand-alignment mode,
  because the line that switches it off is part of the close. The arm may
  still be free: please do not push it away from its resting place. Nobody has recorded yet what
  i1Profiler does when it opens a table in this mode. Please open i1Profiler
  once, let it start the table, and quit it. If it does not bring the arm to
  its resting place, or shows a problem with the table, switch the table off,
  wait ten seconds, switch it on again, and open i1Profiler once more. That is
  a recovery for this case, not a routine step.
* **The touch in the hand-alignment step:** take your hand off the arm before
  you answer. Right after your answer, the program sends the arm home at once.
* **The head might lift or lower during a move.** We do not know whether the
  table does that by itself. Please watch the round measuring opening and tell
  us; that is one of the things we would like to learn.

## What could go wrong in part B, and what to do

At the end, after any stop, the program tells you the table's state as it
knows it from the table's answers: where the arm last read (at its resting
place or out on the table), whether the motors held it or it was free when last
checked, and whether the table is still in the hand-alignment mode. Then it names the recovery for that
state. In short:

* **B1 (the homing):** as step 1 of part A.
* **B2 (the drive to the alignment start):** a move that ends elsewhere, or a
  reading after the short move m1 that fits neither explanation: nothing more
  is sent, and the arm stays out on the table, held. Do not push it. Open
  i1Profiler once, let it start the table, and quit it; if it does not bring
  the arm home, switch the table off, wait ten seconds, switch it on, and open
  i1Profiler once more. If the arm does **not** give way when you touch it
  after f1, the program does not ask you to push it and ends there.
* **From the moment f1 has answered (end of B2) until the end of the job (B6):**
  the table is in the hand-alignment mode. If anything stops the program in
  this time, the table stays in that mode, and nobody has recorded yet what
  i1Profiler does when it opens a table in this mode. Please open i1Profiler
  once, let it start the table, and quit it. If that does not bring the arm to
  its resting place, or shows a problem with the table, switch the table off at
  its power switch, wait ten seconds, switch it on again, and open i1Profiler
  once more. That is a recovery for this case, not a routine step.
* **B3 (you push the arm):** push gently, sideways only, by the instrument
  holder, nothing pressed down. If it resists anywhere, stop pushing and type
  `stop`; never force it. After six tries that do not reach the box, the
  program stops; nothing moved under motor, and the arm is free.
* **B4 (the motors take the arm):** take both hands off the arm before you
  type `yes`. If the arm is not inside the box, or moves between the two
  readings, nothing is sent and nothing moves. If the move ends elsewhere, the
  arm stays out on the table, held, in the hand-alignment mode (see above).
* **B5 (the row):** press **Enter** to stop at the next patch: the program then
  offers to send the arm home from there (the optional homing); if you say
  `no`, nothing more is sent and the arm stays held on row 1. **Ctrl-C** sends
  nothing more at all. If a step ends elsewhere or takes much longer or shorter
  than recorded, nothing more is sent.
* **B6 (home and end of job):** as recorded. If the homing takes longer than
  4.5 s or the arm does not read at its resting place, nothing more is sent.
* **The table never reports that a movement finished:** keep your hands away,
  switch the table off, wait ten seconds, switch it on again, then open
  i1Profiler once and quit it.
* **Anything looks or sounds wrong while the arm moves:** switch the table off
  at its power switch or pull its power plug. That is always allowed and is the
  emergency stop.

## Part C: reading with the instrument (new in 0.5.0)

Part C is where ChromIQ reads for the first time with the i1Pro 2 seated in
the arm. **Several stages are first tries: they may simply fail.** That is
useful too: the program keeps everything about a failure for us, and we
improve the stage from your results.

### How part C works

After the opening (as in parts A and B), part C shows a menu of the stages
that can run now, with about how long each takes, and lists the others with
the reason they cannot run yet. The first stage in the list is our
suggestion. For each stage you choose, it explains what moves, how far and how
long, what is exactly as recorded and what is not, our risk rating, and what
the stage depends on; then you type `yes` (or `back` for the menu). After
each stage it asks whether the table and the instrument did what was described
and what you saw. If you answer `no`, it asks whether anything about the
**table or the arm** was wrong: if yes (or not sure), nothing more moves in
this sitting except, if you want it, the homing (F). If only the instrument or
its readings were not as described, the sitting goes on.

`END` in the menu stops part C. If the arm is out on the table, F is
recommended first.

### Where the arm may go

Every target the program computes lies inside an area in **two parts**. The
**proven part** is **an area of 320 x 230 mm**: the size X-Rite gives for the
first i1iO and the i1iO 3. For the i1iO 2 X-Rite
publishes no size, so for your table the size is our assumption. **Where that
area lies on your table is our estimate**, taken from where the instrument's
measuring opening has actually been in your recordings: its right edge on the
furthest point to the right the opening was ever read at, its front edge on
the furthest point to the front the opening was ever read at, with 5 mm kept
free on every side: table positions X -1384 to 1716 and Y 523 to 2723 (0.1 mm
units). In front of it lies the **front part**, up to table Y 3109 at the
most: up to the frontmost mark of your recorded i1Profiler alignments, and no
further. Nothing is ever sent beyond it. Its place is our estimate too: a
mark is a corner patch of a chart that i1Profiler then measures, so i1Profiler
sends the measuring opening there in normal use, and your table very likely
reaches it (i1Profiler measures charts laid like this), but no reading in your
recordings shows the opening there. So the program goes there only after stage
DZ has felt its way forward in this sitting (see below). The whole rectangle the arm could
sweep on its way must lie inside it too, and every move is computed from a
position read right before it. On your sheet, targets must also lie inside
the three marks you aimed at. The program checks all of this before it sends
a move, and the table line is checked once more right before it goes out. A
move into a part of the table no recording drove the arm to (the front of an
A4 sheet, for example) is announced first and needs its own `yes`.

**If your sheet reaches into the front part, D1 lets you choose.** A sheet laid
as in your i1Profiler sessions does: i1Profiler places a sheet by the alignment
sight, which sits about 3 cm in front of the measuring opening, so your bottom
marks lay up to about 3 cm in front of anywhere the opening itself was ever
read. D1 says so before anything moves and offers two ways: `back` (lay the
sheet that much further back and aim again; nothing new is tried) or `go on`
(with a typed `yes`): then stage DZ first drives the arm forward in steps of
at most 5 mm, checking each one, and only the front limit it reached cleanly
is used for the rest of the sitting.

Strip readings use only the ten speeds i1Profiler used on your table (40 to
138 mm/s; 54 is our suggestion), and spot moves only i1Profiler's chart speed.

### The stages

**C1: Open the instrument with ChromIQ's reader and calibrate it** (about 3 min; depends on: nothing; our risk rating: low). Nothing moves. Choose where to calibrate: `arm` (it stays seated, its opening on the table's white tile) or `own` (you lift it onto its own white calibration tile, then seat it back). The calibration is kept for this sitting.

*What can go wrong and what to do:* The reader cannot start (the program says why: the reader not marked as runnable, macOS's quarantine, no i1Pro 2 or another instrument connected; see "Before the first run"), or the calibration fails. Clean: nothing moved; fix what it names and run C1 again.

**C2: One spot reading of the table's white tile, at the resting place** (about 1 min; depends on: a spot calibration in this sitting (C1, or it calibrates itself); our risk rating: low). Nothing moves. One spot reading of the white tile under the resting arm; the program shows the values.

*What can go wrong and what to do:* The reading fails or looks implausible (for example all zero). Clean: the sitting goes on.

**E1: The recorded row scan of 14 November, replayed exactly (a strip reading)** (about 4 min; depends on: nothing (it calibrates for strip readings itself if C1 did not); our risk rating: medium; a first try). Part B's way out, the arm let go, you push it to the front right (as in part B), then exactly i1Profiler's strip reading of row 1 of your 14 November session, and the recorded end of the job brings the arm home.

*What can go wrong and what to do:* The reader is not ready to start the strip at once: then the strip move is **never sent**, the arm stays held at the row start, and the stage fails cleanly (run F to home it). If the strip move was sent and the instrument's lamp did not start it, the program tells you to **SWITCH THE TABLE OFF** (see below).

**C3: One spot reading at the first patch of the recorded spot row** (about 3 min; depends on: nothing (calibrates itself if needed); our risk rating: medium). Part B's recorded way to the first patch of row 1, then one spot reading there. The arm stays there for C4.

*What can go wrong and what to do:* As part B's steps B1 to B4; a failed reading is clean.

**C4: The recorded spot row, a reading at every patch** (about 2 min (5 from rest); depends on: nothing (C3's way there if needed); our risk rating: low-medium). The 27 recorded moves of row 1 with a spot reading at every patch, then the recorded end of the job. Press Enter between two patches to stop at the next one (clean).

*What can go wrong and what to do:* A move that ends elsewhere or much slower or faster than recorded ends the sitting, as in part B.

**D1: Your ChromIQ i1iO sheet: aim the sight at its three marks** (about 5 min; depends on: nothing (the instrument is not used); our risk rating: medium; a first try). Lay your printed ChromIQ i1iO sheet as ChromIQ printed it for the table while the arm is at rest. The arm goes to the alignment start and is let go; you aim the sight's cross hairs at mark 1, 2 and 3 and type `aimed` at each. Then the program checks the three positions against the sheet and tells you whether every patch and every row of the page lies inside the measuring area this program uses (where it lies on your
table is our estimate, see "Where the arm may go"), and which way to shift the
sheet if not (often a few centimetres towards the back). Nothing moves under motor after the arm is let go.

*What can go wrong and what to do:* The check refuses your aims (marks swapped, a mirrored or turned sheet, a mark missed by more than 2 mm, a mark outside the area): clean, nothing moved. Push the free arm gently aside, lay the sheet again if needed, and run D1 again.

**DZ: Feel the way into the front part of the table, in 5 mm steps** (about 1 min; depends on: D1 accepted in this sitting with a sheet reaching into the front part, and your yes; our risk rating: medium; a first try). Only when D1 found part of your sheet in the front part and you chose `go on`. With your hands off, the arm goes to the front edge of the proven part, right behind your frontmost mark, then forward towards that mark in steps of at most 5 mm (chart speed), the position read after each and a pause of about half a second. Press Enter at any pause to stop. The furthest point reached cleanly is the front limit for the rest of the sitting ("front zone reached: Y ..." in the log and the results). At most 10 steps per run, 3 runs per sitting.

*What can go wrong and what to do:* A step that does not arrive within half a millimetre, or takes longer or shorter than such a move should (for example because the arm met the end of its travel: you may hear the motors buzz or click for a moment): the program stops at once, says where the arm reads, keeps the front limit at the last clean step, and moves nothing more except, if you want it, the homing (F). Please tell us what you heard. If the table never reports a step as finished, switch it off as described below.

**D2: The first computed move: a short one to mark 3** (about 1 min; depends on: D1 accepted in this sitting, the arm not homed since (DZ first if mark 3 lies in the front part); our risk rating: medium; a first try). The first move to a computed target: from the free arm to the position the table reported for mark 3, a few centimetres. You tell us whether the round opening sits on mark 3.

*What can go wrong and what to do:* Your hands still on the arm (it moved between two readings) or the free arm outside the area: clean, nothing moved. A move that ends elsewhere ends the sitting.

**D3: One row of your sheet, a spot reading at every patch** (about 2 min; depends on: D1, and a spot calibration in this sitting (C1, C2, C3 or C4); our risk rating: medium; a first try). Row 1 of your sheet, patch by patch, a spot reading at each. Needs a spot calibration from C1 or C2 to C4 in this sitting.

*What can go wrong and what to do:* As D2. Enter between two patches stops cleanly.

**E2: One row of your sheet as a strip reading** (about 1 min; depends on: D1, and a strip calibration in this sitting (C1 or E1); our risk rating: medium; a first try). Row 1 of your sheet as a strip reading at a recorded speed you choose. Needs a strip calibration (C1 or E1).

*What can go wrong and what to do:* As E1: not ready means no strip move; a strip move that may still wait means SWITCH THE TABLE OFF.

**E3: Your whole page as strip readings, row by row** (about 1 min per 5 rows; depends on: D1, and a strip calibration in this sitting (C1 or E1); our risk rating: medium; a first try). Every row of your page as strip readings, one after the other, with a question after each row whether to go on.

*What can go wrong and what to do:* As E2.

**D4: Your whole page in spot readings, row by row** (about 1 min per row; depends on: D1, and a spot calibration in this sitting; our risk rating: medium; a first try). Every row of your page in spot readings, with a question after each row whether to go on. The longest stage.

*What can go wrong and what to do:* As D3.

**F: Home and end the job** (under 1 min; depends on: the arm out on the table, last read where it stands; our risk rating: low). From wherever the arm stands (held or free, inside the measuring area), i1Profiler's end of a job: the homing, then the lines that switch the hand-alignment mode off, and a last position reading at the resting place.

*What can go wrong and what to do:* The arm outside the measuring area: the homing is not sent (a free arm can be pushed gently back over the middle and F run again). The table refusing the homing ends the sitting; then open i1Profiler once.

The stages build on each other only where they must: D2 to E3 need D1 in the
same sitting (a homing in between means aiming again), D3 and D4 a spot
calibration, E2 and E3 a strip calibration. Everything else can run in any
order. D2, E3 and D4 need DZ first when your sheet reaches into the front part,
and a strip row there first visits its two ends with a spot move each. Part C
sends at most **8680 lines and 3060 movements** in one
sitting, and each stage at most its own number.

### The lines part C adds

Five lines that i1Profiler sent to your table, byte for byte: `p1` (the
position under the alignment sight, sent after each aim), and the four lines
around every one of i1Profiler's 44 recorded strip readings, `c4`, `d1`
(always with the value 365), `a3` and `c3`. And the **computed moves**: the
same form as i1Profiler's recorded moves, only with other target numbers,
inside the measuring area this program uses: `m0` at i1Profiler's chart speed, and the strip
move `m2` at one of the ten recorded speeds. `BYTES.md` lists them with their
recorded places. Nothing else: no memory or configuration writes, no line
never seen in a recording.

### The strip move and the table switch

A strip reading works like this, exactly in i1Profiler's order: the arm
drives to the row start, the reader prepares the instrument, and only when the
reader answers that it can start **at once** is the strip move sent. The table
then **waits** for the instrument's lamp, which the reader switches on right
after; the lamp starts the move. If the lamp did not start it, the table could
be left waiting with no line known to cancel it. Then the program says:

**SWITCH THE TABLE OFF NOW with its power switch.** Do not open i1Profiler
while the table is on (its lamp could start that move). After switching off,
wait ten seconds, switch on, then open i1Profiler once to bring the arm home.

It also leaves a file `SCAN_MOVE_MAY_BE_PENDING.txt` in the results. We do not expect
this, but it is the one state nothing sent can end, so you should know it.

### What the instrument part does on a Mac

ChromIQ's reader opens the i1Pro 2 with the ArgyllCMS instrument library, as
ChromIQ does when you measure by hand. On a Mac that library **closes X-Rite's
background service i1ProDeviceService** if it finds the instrument in use
when it opens it, again and again for up to about two seconds, until it has
the instrument (that is how ArgyllCMS always opens an i1Pro; its own note
says the service starts again by itself). X-Rite's other background program,
xrdd, is not touched. Before the first reader of a sitting starts, the
program tells you this and asks for your yes. What we do not know is whether
i1Profiler finds the i1Pro 2 straight away afterwards on your Mac: if it does
not, unplug the USB cable of the table and the i1Pro 2 from the Mac and plug
it in again (after this program has ended); if it still does not, restart
the Mac.

While this program runs, it keeps the table's USB connection, so i1Profiler
cannot find the table until the program has ended. The
calibration is ArgyllCMS's own, kept in ArgyllCMS's usual file on your Mac,
not in the instrument.

## Before you start

You need a Mac, the i1iO 2 with its i1Pro 2, and Python 3.8 or newer. The
same set-up as for the earlier programs works (the `venv` folder and
Homebrew's libusb). Unpack the zip and open the Terminal in that folder.

### Practice first (nothing is opened)

```
python3 i1io_session.py
python3 i1io_session.py --sim cold
```

These run on a **simulated table**; nothing is sent to any device. Choose
`c` to practise part C: it uses a simulated instrument and a demo sheet that
comes with this package (`demo/demo-sheet.i1io.json`), and writes a results
zip like the real run.

### Before the first run of part C: the reader

Part C starts ChromIQ's reader `bin/chromiq-chartread` from this package. macOS
marks everything downloaded from the internet, and then refuses to start such
a program from the Terminal. In the Terminal, in this folder, once:

```
xattr -d com.apple.quarantine bin/chromiq-chartread
chmod +x bin/chromiq-chartread
```

The first line removes that mark (if it says "No such xattr", the mark was not
there, which is fine); the second marks the reader as runnable. If either is
needed and missing, part C says so before it starts the reader, and nothing is
sent. The reader runs on Apple silicon and Intel Macs with macOS 13 or newer.

For D1 to E3 you need your printed **ChromIQ i1iO sheet** and its file
(ending `.i1io.json`, beside the `.ti2` in the run folder of your ChromIQ
project). Start the program with `--sheet` and that file, or drag the file
into the Terminal window when D1 asks for it. If your sheet has more than one
page, add `--page 2` and so on.

### What to install for the real table

```
HOMEBREW_NO_AUTO_UPDATE=1 brew install libusb
python3 -m venv venv
venv/bin/python3 -m pip install --no-cache-dir pyusb==1.2.1
```

### Preparing the table

1. Open i1Profiler once, let it start the table, and quit it. Then start the
   program within a minute or two.
2. i1Profiler must not be running. X-Rite's background helpers can keep
   running; please do not try to stop them by hand.
3. The arm at its resting place, the i1Pro 2 seated in its holder.
4. **The table empty** except for the chart or sheet a stage asks for: for
   parts A and B no paper, no chart, nothing in the way of the arm over the
   whole table; in part C only the chart or sheet the stage asks for, laid
   where it says.
5. The power switch or plug within reach.

### The real run

```
venv/bin/python3 i1io_session.py --real
```

It explains the risks, asks five short questions and three more about the
time since you quit i1Profiler and the lights (please do not touch the arm
before the first homing), and asks you to type `I understand that this moves
my table`. Then it asks which part you want (`a`, `b`, `c` or `end`; for `b`,
three questions about your part A or 0.3.1 run; for `c`, the same three and one
about part B), opens the table and offers the steps or, in part C, the menu of
stages. For part C with your sheet:

```
venv/bin/python3 i1io_session.py --real --sheet /path/to/your-chart.i1io.json
```
 Answer
each question by typing the whole word (`yes`, `skip`, `end`, `no`, `not sure`,
`stop`, `holds`, `free`, `placed`) and pressing Enter.

### How to stop

* Type `skip` or `end` when a step is offered, or `stop` at a question.
* Press **Ctrl-C** at any time: after Ctrl-C has been noticed, the program
  sends nothing more. A movement that has already begun is not stopped by
  Ctrl-C.
* **Switch the table off or pull its power plug**, at any moment.

If the table is in use by another program, the program says so, names the
program if macOS names it, and lists what usually helps; nothing is sent.

## What to send back

**Part C: the ONE results zip** in the folder you started it from
(`i1io-session-<date>-<time>-results.zip`). It holds the log and the results
folder: every stage's result, the readings (spot readings and strip readings,
as `.ti3` files ChromIQ can read), the plans and positions of every row, and
the raw reading streams. It holds no serial number and nothing from the
memory of the table or the instrument. If you have **an i1Profiler measurement
of the same sheet or chart** (for E1, C3 and C4 your iO chart of 14 November;
for D and E stages your ChromIQ sheet measured in i1Profiler's own mode), please
send it too: comparing the two is how we learn whether ChromIQ's readings on
the table are right.

For parts A and B, the log file in the folder you started it from (`i1io-session-<date>-<time>.txt`):
every line sent and received with times, how long each movement took, every
position the arm reported, and your answers. It holds **no serial number**.
Please read it first, then send it the private way you agreed with Basti, or
attach it to issue #129, with a few words about what you saw at each step. A
short phone video of part B from the side, at table height, would also help a
lot (the glider ring and the mat in view), but only if it is easy and you keep
your hands away from the arm. If anything worries you, simply stop; one step is
already a help.

If the session ends with the table still in the hand-alignment mode, or without
the close in part A, open i1Profiler once afterwards and quit it (see "What
could go wrong" above).

## Licence

GPL-3.0-or-later, like ChromIQ itself (see `LICENSE`).
Source: https://github.com/itsab1989/ChromIQ (folder `tools/i1io_session`).

*Written by Claude, the AI assistant working with Basti.*
