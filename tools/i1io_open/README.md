# ChromIQ i1iO test program 0.2.2 (open and close a started table like i1Profiler)

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
* it asks you to **feel gently whether the arm is held** three times: once
  before it opens anything, and once before and once after it lets go of the
  table's USB connection.

## What changed since 0.2.1

Thank you for running 0.2.1 so carefully. Here is what we learned from your
logs and what this version does differently.

* **We got the range wrong a second time, and this time we changed how it is
  made.** Version 0.2.1 opened your table fine and then stopped before the
  homing, because the arm read X 1101, Y 55 (in tenths of a millimetre, so 5.5
  mm from zero), and 0.2.1 only went on up to Y 50. Your table did nothing
  wrong. The arm's reading at rest is not a fixed spot: it is about 0 right
  after a homing and creeps away slowly the longer the arm stands (22 to 37
  within minutes in the recordings, 41 to 55 after long waits). Both earlier
  limits were taken from the largest reading we had seen so far, and both were
  beaten later. **This version no longer guesses.** It sends the homing only
  from the places i1Profiler itself was recorded sending it from (X 1102, Y 0
  to 47), with one tenth of a millimetre around them: X 1101 to 1103, Y -1 to
  48. That is stricter than before. If your arm reads anything else, the
  program stops right there and moves nothing. That is a planned ending, not a
  fault, and the program tells you so. The reason we do not simply allow more:
  in one recording, with the arm further away, i1Profiler did not send this
  homing at all but drove the arm out first, and nobody knows where its own
  limit lies.
* **Best chance of a complete run:** open i1Profiler, let it start the table,
  quit it, and start this program straight away. In the recordings, in the
  first three minutes after i1Profiler's own homing the arm read Y 22 to 37.
  We cannot promise it, because nobody has measured how fast it creeps once
  i1Profiler has quit.
* **One extra touch, before anything is opened.** With 0.2.1 you found the arm
  free at rest, both while the program still held the USB connection and
  afterwards. At the same moment the table had answered the question we used to
  read as "the motors hold the arm" with 00. So that answer does not mean what
  we thought, and the program no longer says so. The new first touch, made
  before the program opens anything (best right after you quit i1Profiler),
  tells us whether a free arm is simply how i1Profiler leaves the table. The
  program also asks roughly how many minutes ago you quit i1Profiler. No new
  line is sent for any of this.
* **A table that is in use by another program.** Twice the Mac did not let
  0.2.1 open the table ("Access denied"). Nothing was sent then, and your table
  was fine. That message comes from the Mac, not from the table: another
  program was holding the table's USB connection. It was not i1Profiler as far
  as 0.2.1 could see, and X-Rite Device Services was running also when it
  worked, so we do not know which program it was. This version asks macOS which
  program holds the table (it only reads macOS's list; it opens nothing and
  touches no program), names it, and explains step by step what usually helps.
* **After a stop, the table is not closed, and the program now says so.**
  i1Profiler has only been recorded sending its two closing lines right after
  its homing, so after any stop this program sends nothing at all. Ending
  without them is the same as when i1Profiler is force-quit or its USB cable is
  pulled. Three earlier runs on your table ended this way, and each time the
  next opening worked normally.
* **Smaller things:** a Ctrl-C or a closed Terminal window during the first
  questions is now written into the log (your first run's log simply ended);
  and if the program is started without pyusb, it shows the exact command to
  use.

The lines it sends and their order are the same as in 0.2.1.

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

1. **Open i1Profiler once, wait until it shows the table, and quit it.** That
   starts the table if it was switched on, and it sends the arm to its resting
   place. Then start this program within a minute or two (see "What changed
   since 0.2.1" for why). (If the table was just switched on and you skip
   this, the program simply stops after reading and tells you so; nothing
   moves.)
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
on). Then, **before it opens anything**, it asks you for the first gentle touch
(the same touch as described below) and roughly how many minutes ago you quit
i1Profiler. Then it asks you to type this sentence:

```
I understand that this moves my table
```

Then it opens the table (nothing moves). Before the homing it stops, tells
you exactly what will move, and asks `Send it now?`. Right after your yes it
reads where the arm is: if that is not where i1Profiler itself sent the homing
from (X 1101 to 1103, Y -1 to 48), it stops there and moves nothing (see above).
Otherwise it sends the homing, and afterwards asks you to look at the arm. If
the arm is at its resting place, it closes the table.

Then it sends nothing more, and asks you twice more to put one finger on the
instrument holder and push it very gently towards the front of the table (the
way the arm travels over the table), as if to move it by about a millimetre,
then let go at once. Do not force it. Then you say whether the arm **holds**
its place (it resists your finger, or springs back when you let go) or moves
**free**ly (it gives way with almost no effort, as when the table is switched
off): once while the program still holds the table's USB connection, and once
ten seconds after it has let go of it. Answer each question by typing the whole
word or words (`yes`, `no`, `not sure`, `stop`, `holds`, `free`, `skip`) and
pressing Enter.

### If the arm is loose afterwards

As far as we know, that is the same harmless state as a table that is switched
off. Please do not push it around. Leave the arm where it is, at its resting
place. Then open i1Profiler once, let it start the table as usual, and quit it.
If you have a moment, touch the holder gently once more about ten minutes after
the run and add a line to the log about what you felt.

### If the table is in use by another program

If the Mac does not let the program open the table, nothing is sent, and the
program shows which program macOS says is holding it (if macOS says). What
usually helps, one step at a time:

1. If i1Profiler is open, quit it (i1Profiler menu, Quit i1Profiler).
2. Wait a minute and start the program again.
3. If the table is still in use: open i1Profiler, wait until it shows the
   table, quit it, and start the program again straight away.
4. If it is still in use after that, restarting the Mac frees it.

Please do not try to stop X-Rite's background helpers by hand; the program
never touches them either.

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

If the program stops, it does not send i1Profiler's closing lines (they are
recorded only right after the homing). That is the same as when i1Profiler is
force-quit, and so far your table has always opened normally the next time.

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
* when you found the arm held or loose (the program asks three times;
  anything you felt later is welcome too, with the time);
* any sounds, and when;
* anything unexpected at all.

Thank you for trying it.

---

## Licence

GPL-3.0-or-later, like ChromIQ itself (see `LICENSE`).
Source: https://github.com/itsab1989/ChromIQ (folder `tools/i1io_open`).

*Written by Claude, the AI assistant working with Basti.*
