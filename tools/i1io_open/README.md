# ChromIQ i1iO test program 0.2.0 (open and close the table like i1Profiler)

This is the second small test program for the **X-Rite i1iO 2** scanning table
with an **i1Pro 2**, written for ChromIQ issue #129 from the USB recordings a
table owner made with i1Profiler. The first one (0.1.x) asked the table a few
questions and sent the arm home once. This one does what i1Profiler does when
it connects to the table and when you quit it, and nothing more:

* it **opens** the table with i1Profiler's own opening lines;
* if the table has **just been switched on**, it sends i1Profiler's
  **start-up line** (about 3 seconds; the arm ends at its resting place);
* it sends the arm to its **resting place**, where it already is (about a
  quarter of a second; the arm should barely move);
* it **closes** the table with i1Profiler's own two closing lines.

**It never measures, never talks to the i1Pro 2, and never moves the arm out
over the table.** It is not part of the ChromIQ app and does not need it.

Why this step: in the first test, a freshly switched-on table refused the
program until i1Profiler had been opened once. Your cold-start recording
showed why: i1Profiler sends one start-up line to such a table first. This
program sends that line in exactly the situation i1Profiler sent it, so we can
see whether ChromIQ can start the table by itself.

Nothing here is promised. Whether you try it is entirely your choice, there is
no warranty, and you can stop at every step.

---

## What it sends, line by line

The program can send only **twelve different lines** to the table, and each
one is a line i1Profiler itself sent to your table in your recordings, byte for
byte, in the same order. The file `BYTES.md` lists them with the exact place in
your recordings where i1Profiler sent each one. `python3 i1io_open.py --plan`
prints the whole sequence; `--dry-run` prints it with every byte.

| Line | What it does | Moves? |
|---|---|---|
| `;a133` | asks who the table is (twice) | no |
| `;k228` | asks a fixed value the table always gives | no |
| `;u8000060000100d1` | asks for part 1 of the table's memory block | no |
| `;u8000061000068c3` | asks for part 2 of the memory block | no |
| `;a034` | asks whether the table has just been switched on (111800) or is started (130000) | no |
| `;i02c` | **start-up**, only if the table has just been switched on | **yes, about 3 s** |
| `;s022` | asks for the status | no |
| `;f42b` | asks whether the motors hold the arm (four times) | no |
| `;p025` | asks where the arm is | no |
| `;i12b` | **go to the resting place** (the arm is already there) | **barely, about 0.25 s** |
| `;f02f` | first closing line | no |
| `;f32c` | second closing line | no |

About the memory block: i1Profiler reads it every time it connects, so this
program does too, to keep the same order. It holds the table's serial number.
The program checks only its length and first eight bytes, and **never writes
it down or shows it**.

About the start-up line: i1Profiler sent it once in your recordings, right
after the table had been switched on, with the arm resting at its parking
place. It took 3.2 seconds, and the arm was at its resting place afterwards.
**What the arm does during those 3 seconds is not known**: it may move a
little away and back, as tables do when they find their reference point. That
is one of the things we hope to learn, so please watch it. The program sends
this line **only** when the table says it has just been switched on, and
**only** if you have told it that the arm was at its resting place when you
switched the table on and that nobody has pushed it since.

**If anything is not as expected** (no answer, a strange or unknown answer,
an error, the arm not where it should be, an answer much slower than with
i1Profiler, the cable gone) the program stops and sends **nothing more at
all**, not even the closing lines.

---

## Before you start

You need a Mac, the i1iO 2 with its i1Pro 2, and Python 3.8 or newer. It works
on Apple silicon and Intel Macs; your first test ran on macOS 26 with Python
3.15. If you still have the folder of the first test program with its `venv`
folder and Homebrew's libusb, you can use the same commands below; nothing
new needs to be installed.

Check Python in the Terminal app: `python3 --version`

Unpack the zip, then open the Terminal in that folder (type `cd ` with a space,
drag the folder onto the Terminal window, press Enter). The program is a plain
Python file, so macOS does not ask about an "unidentified developer": nothing
needs to be unblocked or signed.

---

## 1. The practice runs (nothing is opened)

```
python3 i1io_open.py
python3 i1io_open.py --sim warm
```

These run on a **simulated table**: the first as if it had just been switched
on, the second as if it were already started. Nothing is opened and nothing
is sent to any device, so the table can stay switched off. They ask the same
questions as the real run and print every line the real run would send and
receive. Each writes a log file ending in `-simulated-cold.txt` or
`-simulated-warm.txt`.

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
* The program leaves one empty file, `chromiq-i1io-open.lock`, in your
  temporary folder, so that two copies never run at once. macOS clears it.

---

## 3. Preparing the table

The most useful run is a **cold start**, because that is the new part:

1. **Quit i1Profiler.** The program refuses to start while it runs. X-Rite's
   background helpers (i1ProfilerTray, X-Rite Device Services) can keep
   running; please do not try to stop them by hand.
2. Make sure the **arm is at its resting place**, where i1Profiler leaves it
   when you quit it: the instrument holder over the table's small white tile,
   with the round measuring opening resting on that tile.
3. **Leave the i1Pro 2 seated in the arm's holder and connected**, as when you
   use it with i1Profiler.
4. **Take everything off the table**: no paper, no chart, nothing.
5. **Switch the table off** at its power switch, wait about ten seconds, and
   **switch it on again**. Do not touch the arm. Wait until it is quiet.
6. Have the table's **power switch or plug** within reach, and look at the arm.

If you skip steps 5 and the table was already started, the program simply
leaves out the start-up line (a "warm" run). That is useful too.

---

## 4. The real run

```
venv/bin/python3 i1io_open.py --real
```

It checks that pyusb and libusb are there, explains the risks, and asks five
short questions (power within reach, instrument seated, table empty, arm at
its resting place, arm not moved since the table was switched on). Then it
asks you to type this sentence:

```
I understand that this moves my table
```

Then it opens the table (nothing moves). Before the first movement it stops,
tells you exactly what will move and for how long, and asks
`Send it now?`. On a cold table, your yes covers both movements (the start-up,
then right after it the homing, as i1Profiler does them back to back). On a
warm table it covers the homing only.

Afterwards it asks you to look at the arm, and on a cold table what the arm
did during the start-up. If the arm is at its resting place, it closes the
table and finishes. Answer each question by typing the whole word or words
(`yes`, `no`, `not sure`, `moved a little`, `stop`, ...) and pressing Enter.

### How to stop

* Type `stop` (or `no`) at any question.
* Press **Ctrl-C** at any time. After Ctrl-C has been noticed, the program
  sends **nothing more** to the table. A movement that has already begun is not
  stopped by Ctrl-C.
* **Switch the table off or pull its power plug.** Always allowed, at any
  moment. Pulling the USB cable alone does not stop a movement: the table has
  its own power supply. (Your cold-start recording shows that a table that
  has just been switched on answers a few questions and then waits for its
  start-up line. What the table does at the moment it is switched on, or off
  in the middle of a movement, no recording shows.)

If the program stops and the arm is not at its resting place, it stays where
it is. To bring it home, open i1Profiler once, let it connect to the table,
and quit it. Please do not start this program again before that.

If the program says the table **never reported that its movement had
finished**, keep your hands away from the arm, switch the table off, wait ten
seconds and switch it on again before you open i1Profiler.

---

## 5. What to send back

The program writes a log file into its folder, named
`i1io-open-<date>-<time>.txt`. It holds every line sent and received, with
times, your answers, and the macOS, Python, pyusb and libusb versions. It holds
**no serial number** (the two memory answers appear only as "not written
down"). Please **read it first**, then send the log file itself the private
way you agreed with Basti, or attach it to issue #129 if you prefer, with a
few words:

* cold or warm run (did you switch the table off and on before?);
* what the arm did during the start-up, and during the homing;
* any sounds, and when;
* anything unexpected at all.

Thank you for trying it.

---

## Licence

GPL-3.0-or-later, like ChromIQ itself (see `LICENSE`).
Source: https://github.com/itsab1989/ChromIQ (folder `tools/i1io_open`).

*Written by Claude, the AI assistant working with Basti.*
