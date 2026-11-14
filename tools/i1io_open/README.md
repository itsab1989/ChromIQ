# ChromIQ i1iO test program 0.2.1 (open and close a started table like i1Profiler)

**This is an unofficial test program. It is not from X-Rite, and X-Rite has
nothing to do with it.** Running it is entirely your choice, without any
warranty. Keep your hands and everything else away from the arm while it moves.

This is the second small test program for the **X-Rite i1iO 2** scanning table
with an **i1Pro 2**, written for ChromIQ issue #129 from the USB recordings a
table owner made with i1Profiler. The first one (0.1.x) asked the table a few
questions and sent the arm home once. This one does what i1Profiler does when
it connects to a table that is already started, and when you quit it:

* it **opens** the table with i1Profiler's own opening lines;
* it sends the arm to its **resting place** once, where it already is,
  exactly as i1Profiler did right before it closed the table in your
  recordings (the arm should barely move);
* it **closes** the table with i1Profiler's own two closing lines;
* it asks you to **feel gently whether the arm is held**, once before and once
  after it lets go of the table's USB connection.

**What changed since 0.2.0.** On your table, version 0.2.0 opened the table and
sent the arm home, then read the arm's position (X 1102, Y 19, which is its
resting place) and stopped, because it expected a value between Y -3 and Y 8.
That expectation came from too few readings and was wrong; your table did
nothing wrong. This version checks the position before its one homing against
everything any recording has ever read at the resting place (X 1097 to 1107,
Y -5 to 50), and it reads no position after the homing, because i1Profiler
never asks for the position right before it closes the table. Afterwards you found the arm **loose**, as when the table is switched
off. We do not know yet why; the two touch questions at the end are there to
find out when it happens.

If the table **has just been switched on**, it needs a start-up first, which
this version does **not** send: the program then stops after the opening's
reading lines, moves nothing, and asks you to open i1Profiler once (so that
i1Profiler starts the table), quit it, and run the program again.

**It never measures, never talks to the i1Pro 2, and never moves the arm out
over the table.** So the instrument's own light will not come on, unlike when
i1Profiler starts the table. It is not part of the ChromIQ app and does not need it.

Nothing here is promised, and you can stop at every step.

---

## What it sends, line by line

The program can send only **eleven different lines** to the table. Each one is
a line i1Profiler itself sent to your table in your recordings, byte for byte,
and every stretch of up to ten lines that follow each other here also follows in
the same order in your recordings. The opening is i1Profiler's opening; the
homing (status, position, homing, status), the pause and the closing are
exactly how i1Profiler ended one of your sessions. The file `BYTES.md`
lists every line with the exact place in your recordings where i1Profiler sent
it. `python3 i1io_open.py --plan` prints the whole sequence; `--dry-run` prints
it with every byte.

| Line | What it does (as far as we know) | Moves? |
|---|---|---|
| `;a133` | asks who the table is (twice) | no |
| `;k228` | asks a fixed value the table always gives | no |
| `;u8000060000100d1` | asks for part 1 of the table's memory block | no |
| `;u8000061000068c3` | asks for part 2 of the memory block | no |
| `;a034` | we believe it tells whether the table has just been switched on (111800) or is started (130000) | no |
| `;s022` | asks for the status | no |
| `;f42b` | we believe it asks whether the motors hold the arm (four times) | no |
| `;p025` | asks where the arm is (before the homing) | no |
| `;i12b` | **go to the resting place** (the arm is already there), once | **barely, about a third of a second** |
| `;f02f` | first closing line | no |
| `;f32c` | second closing line | no |

After your yes, the program asks for the status and where the arm is, and
sends the homing at once if the arm is at its resting place, as i1Profiler
does. On your table, with version 0.2.0, the homing took about a third of a
second.

About the memory block: i1Profiler reads it every time it connects, so this
program does too, to keep the same order. It holds the table's serial number.
The program checks only its length and first eight bytes, and **never writes
it down or shows it**.

About the measuring head: the program sends no line of its own for the head.
Whether the table lifts and lowers it by itself as part of the homing is not
known; with the first program the arm moved very little and nothing unusual
was seen.

**If anything is not as expected** (no answer, a strange or unknown answer,
an error, the arm not where it should be, an answer much slower than with
i1Profiler, the cable gone) the program stops and sends **nothing more at
all**, not even the closing lines.

---

## Before you start

You need a Mac (Apple silicon or Intel), the i1iO 2 with its i1Pro 2, and
Python 3.8 or newer. If you still have the folder of the first test program
with its `venv` folder and Homebrew's libusb, the same set-up works here.

Check Python in the Terminal app: `python3 --version`

Unpack the zip, then open the Terminal in that folder (type `cd ` with a space,
drag the folder onto the Terminal window, press Enter). The program is a plain
Python file, so macOS does not ask about an "unidentified developer": nothing
needs to be unblocked or signed.

---

## 1. The practice runs (nothing is opened)

```
python3 i1io_open.py
python3 i1io_open.py --sim cold
```

These run on a **simulated table**: the first as if it were already started,
the second as if it had just been switched on (it shows the stop and the
advice). Nothing is opened and nothing is sent to any device, so the table can
stay switched off. Each writes a log file ending in `-simulated-warm.txt` or
`-simulated-cold.txt`.

---

## 2. What to install for the real table

The real run needs the **libusb** library and the Python package **pyusb**,
the same as for the first test program:

```
HOMEBREW_NO_AUTO_UPDATE=1 brew install libusb
python3 -m venv venv
venv/bin/python3 -m pip install --no-cache-dir pyusb==1.2.1
```

No driver is installed: the program talks to the table's USB chip directly
through libusb, as the first test program did on your Mac.

### How to undo it all afterwards

* pyusb: delete the program's folder (the `venv` folder inside it holds it).
* libusb: only if you installed it for these tests, `brew uninstall libusb`.
* The program leaves one empty file, `chromiq-i1io-open.lock`, in your Mac's
  temporary folder (`$TMPDIR`), so that two copies never run at once. macOS
  clears it by itself.

---

## 3. Preparing the table

1. **If the table has been switched on since you last used i1Profiler: open
   i1Profiler once, wait until it shows the table, and quit it.** That starts
   the table. (If you skip this, the program simply stops after reading and
   tells you so; nothing moves.)
2. **Quit i1Profiler.** The program refuses to start while it runs. X-Rite's
   background helpers (i1ProfilerTray, X-Rite Device Services) can keep
   running; please do not try to stop them by hand.
3. Make sure the **arm is at its resting place**, where i1Profiler leaves it
   when you quit it: the instrument holder over the table's small white tile,
   with the round measuring opening resting on that tile.
4. **Leave the i1Pro 2 seated in the arm's holder and connected**, as when you
   use it with i1Profiler.
5. **Take everything off the table**: no paper, no chart, nothing.
6. Have the table's **power switch or plug** within reach, and look at the arm.

---

## 4. The real run

```
venv/bin/python3 i1io_open.py --real
```

It checks that pyusb and libusb are there, explains the risks, and asks five
short questions (power within reach, instrument seated, table empty, arm at
its resting place, i1Profiler connected and quit since the table was switched
on). Then it asks you to type this sentence:

```
I understand that this moves my table
```

Then it opens the table (nothing moves). Before the homing it stops, tells
you exactly what will move, and asks `Send it now?`. Afterwards it asks you to
look at the arm. If the arm is at its resting place, it closes the table.

Then it sends nothing more, and asks you twice to touch the instrument holder
very gently with one finger, sideways, as if to move it by about a millimetre,
and to say whether the arm **holds** its place or moves **free**ly: once while
the program still holds the table's USB connection, and once ten seconds after
it has let go of it. Do not force it. Answer each question by typing the whole
word or words (`yes`, `no`, `not sure`, `stop`, `holds`, `free`, `skip`) and
pressing Enter.

### If the arm is loose afterwards

As far as we know, that is the same harmless state as a table that is switched
off. Please do not push it around. Leave the arm where it is, at its resting
place. Then open i1Profiler once, let it start the table as usual, and quit it.
If you have a moment, touch the holder gently once more about ten minutes after
the run and add a line to the log about what you felt.

### How to stop

* Keep your hands and everything else away from the arm while it moves.
* Type `stop` (or `no`) at any question.
* Press **Ctrl-C** at any time. After Ctrl-C has been noticed, the program
  sends **nothing more** to the table. A movement that has already begun is not
  stopped by Ctrl-C.
* **Switch the table off or pull its power plug.** Always allowed, at any
  moment. Pulling the USB cable is not a way to stop a movement: the table has
  its own power supply. (What the table does when it is switched off in the
  middle of a movement, no recording shows.)

If the program stops and the arm is not at its resting place, it stays where
it is. To bring it home, open i1Profiler once, let it connect to the table,
and quit it. Please do not start this program again before that.

If the program says the table **never reported that its movement had
finished**, keep your hands away from the arm, switch the table off, wait ten
seconds and switch it on again before you open i1Profiler.

---

## 5. What to send back

The program writes a log file into the folder you started it from (the
program's folder, if you followed the steps above), named
`i1io-open-<date>-<time>.txt`. It holds every line sent and received, with
times, your answers, and the macOS, Python, pyusb and libusb versions. It holds
**no serial number** (the two memory answers appear only as "not written
down"). Please **read it first**, then send the log file itself the private
way you agreed with Basti, or attach it to issue #129 if you prefer, with a
few words:

* had the table been switched off and on before, and had i1Profiler been
  opened since;
* what the arm did during the homing;
* when you found the arm held or loose (the program asks twice; anything you
  felt later is welcome too, with the time);
* any sounds, and when;
* anything unexpected at all.

Thank you for trying it.

---

## Licence

GPL-3.0-or-later, like ChromIQ itself (see `LICENSE`).
Source: https://github.com/itsab1989/ChromIQ (folder `tools/i1io_open`).

*Written by Claude, the AI assistant working with Basti.*
