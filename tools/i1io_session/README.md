# ChromIQ i1iO session test program 0.3.1 (a few recorded steps, one at a time)

**This is an unofficial test program. It is not from X-Rite, and X-Rite has
nothing to do with it.** Running it is entirely your choice, at every single
step, without any warranty. Keep your hands and everything else away from the
arm while it moves, keep the table empty, and keep its power switch within
reach.

This is the next small test program for the **X-Rite i1iO 2** scanning table
with an **i1Pro 2**, written for ChromIQ issue #129 from the USB recordings you
made with i1Profiler. The earlier programs (0.1.0 to 0.2.1) only opened the
table, sent the arm home where it already was, and closed it. This one goes
further, because we would like to learn more from one sitting and save you
some back and forth: after opening the table it **offers a few steps, one at a
time**. Before each step it tells you what will move, how far, how long it took
when i1Profiler did it, what is exactly as recorded and what goes one step
beyond a recording. You type `yes` to run it, `skip` to leave it out, or `end`
to finish. After each step it asks what you saw, heard and felt.

**It never measures, never talks to the i1Pro 2, never writes anything into
the table's memory, and sends no line of its own for the measuring head.** It
is not part of the ChromIQ app and does not need it.

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

## The steps

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

The person is never asked anything while the arm is away from its resting
place: once a step starts, it runs until the arm is home again (or until
anything is not as expected, and then nothing more is sent).

## Every line it can send

It can send only **sixteen different lines**. Each one is a line i1Profiler
itself sent to your table in your recordings, byte for byte. `BYTES.md` lists
each with the exact places in your recordings. `python3 i1io_session.py
--plan` prints every step and line; `--dry-run` adds every byte.

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

**What it never sends:** the start-up of a table just switched on, the move to
the alignment start (its meaning is not clear enough), the scanning lines that
only occur between "arm over a patch" and "reading" (one of them may lower the
head), any write to any memory, any target the arm was not driven to in your
recordings, and any other speed.

## What could go wrong, and what to do

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

## Before you start

You need a Mac, the i1iO 2 with its i1Pro 2, and Python 3.8 or newer. The
same set-up as for the earlier programs works (the `venv` folder and
Homebrew's libusb). Unpack the zip and open the Terminal in that folder.

### Practice first (nothing is opened)

```
python3 i1io_session.py
python3 i1io_session.py --sim cold
```

These run on a **simulated table**; nothing is sent to any device.

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
4. **The table empty**: no paper, no chart, nothing in the way of the arm over
   the whole table.
5. The power switch or plug within reach.

### The real run

```
venv/bin/python3 i1io_session.py --real
```

It explains the risks, asks five short questions and three more about the
time since you quit i1Profiler and the lights (please do not touch the arm
before the first homing), and asks you to type `I understand that this moves
my table`. Then it opens the table and offers the steps. Answer
each question by typing the whole word (`yes`, `skip`, `end`, `no`, `not sure`,
`stop`, `holds`, `free`) and pressing Enter.

### How to stop

* Type `skip` or `end` when a step is offered, or `stop` at a question.
* Press **Ctrl-C** at any time: after Ctrl-C has been noticed, the program
  sends nothing more. A movement that has already begun is not stopped by
  Ctrl-C.
* **Switch the table off or pull its power plug**, at any moment.

If the table is in use by another program, the program says so, names the
program if macOS names it, and lists what usually helps; nothing is sent.

## What to send back

The log file in the folder you started it from (`i1io-session-<date>-<time>.txt`):
every line sent and received with times, how long each movement took, and your
answers. It holds **no serial number**. Please read it first, then send it the
private way you agreed with Basti, or attach it to issue #129, with a few words
about what you saw at each step. If anything worries you, simply stop; one
step is already a help.

If the session ends without the close, open i1Profiler once afterwards and quit
it. After the hand-alignment step, please run the close; if you could not, see
"What could go wrong" above.

## Licence

GPL-3.0-or-later, like ChromIQ itself (see `LICENSE`).
Source: https://github.com/itsab1989/ChromIQ (folder `tools/i1io_session`).

*Written by Claude, the AI assistant working with Basti.*
