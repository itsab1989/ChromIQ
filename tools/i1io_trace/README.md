# ChromIQ i1iO test program 0.1.1 (a first sign of life)

This is a very small test program for the **X-Rite i1iO 2** scanning table
with an **i1Pro 2**. It was written for ChromIQ issue #129, from the USB
recordings a table owner made with i1Profiler. It is the first time anything
other than X-Rite's software talks to the table, so it does almost nothing on
purpose: it reads the table's identity, status and position, and asks the
table **once** to run to its resting place, where the arm already is. The arm
should barely move. **It never measures.**

It is not part of the ChromIQ app, and it does not need ChromIQ.

**Before the real run, after switching the table on: open i1Profiler once,
wait until it shows the table, and quit it.** On the first real test, the
table refused the program's status question until i1Profiler had been opened once
(most likely because i1Profiler does a start-up step this program leaves out).
If the table refuses anyway, the program says so, explains this, and stops
without sending anything more.

Nothing here is promised. Whether you try it is entirely your choice, there is
no warranty, and you can stop at every step. Nobody on the ChromIQ project owns
a table, so you would be the first person ever to run it on one.

---

## What it does, and what it never does

With `--real` the program does exactly this, and nothing else:

1. It **reads** the table's identity (twice), its status, whether the motors
   hold the arm, and where the arm is. Nothing moves. If the table is not
   exactly the model the recordings came from, or the motors do not hold the
   arm, or the arm is not at its resting place, the program stops here.
2. It asks you to look: is the arm at its resting place? And, as a separate
   question: is the table empty?
3. It reads the motors and the position once more, and then sends the one line
   that can make the arm move: **"go to your resting place"**. The arm is
   already there, so it should move very little or not at all; you may hear
   the motors for a moment. Then it reads the position (it must be the resting
   place) and the motors once more.
4. It asks you to look under the instrument holder: does it rest on the white
   tile, or is there a gap?

That is all. It can send only **five different lines** to the table, and
every one of them is a line i1Profiler itself sent to the tester's table in the
recordings, byte for byte:

| Line | What it does |
|---|---|
| `;a133` | asks the table who it is (nothing moves) |
| `;s022` | asks for the table's status (nothing moves) |
| `;f42b` | asks whether the motors hold the arm (nothing moves) |
| `;p025` | asks where the arm is (nothing moves) |
| `;i12b` | asks the arm to go to its resting place (sent once, only while it is already there) |

The program contains **no command for any other movement**. `python3
i1io_trace.py --plan` prints the whole sequence, in order.

When i1Profiler connects to the table, it also sends a few lines that only
fetch data from the table before it sends the arm home. This program leaves
those out. If the table needed them first, the most likely result is an error
reply and a harmless stop, and that would be a useful answer too.

**It never** sends a command of its own to lower or lift the measuring head,
never measures, never talks to the i1Pro 2 at all, and never reads or writes
the table's memory. It never reads the table's serial number. It cannot see
the measuring head, which is why it asks you to look.

**If anything is not as expected** (no answer, a strange answer, an error, the
arm not where it should be, the cable gone) the program stops and sends
**nothing more at all**.

(Words like "back of the table" and "resting place" are our reading of the
recordings; the table itself only reports numbers.)

---

## Before you start

You need a Mac, the i1iO 2 with its i1Pro 2, and Python 3.

Check Python in the Terminal app:

```
python3 --version
```

If macOS offers to install the "command line developer tools" at this point,
that is Apple's own package and includes Python; you can accept it. Python from
Homebrew (`brew install python`) works too.

Unpack the zip, then open the Terminal in that folder (type `cd ` with a space,
drag the folder onto the Terminal window, then press Enter).

---

## 1. The practice run (nothing is opened)

```
python3 i1io_trace.py
```

This runs on a **simulated table**. Nothing is opened and nothing is sent to
any device, so the table can even stay switched off. It asks you the same
questions as the real run and prints every line the real run would send and
receive. It writes a log file ending in `-simulated.txt`.

---

## 2. What to install for the real table

The real run needs the **libusb** library and the Python package **pyusb**.
libusb comes from Homebrew. If you do not have Homebrew, please run only the
practice test and tell us; we will find another way.

```
HOMEBREW_NO_AUTO_UPDATE=1 brew install libusb
python3 -m venv venv
venv/bin/python3 -m pip install --no-cache-dir pyusb==1.2.1
```

If Homebrew says libusb is already installed, please note that, so you know
not to remove it later. The last two lines put pyusb into a small folder called
`venv` inside the program's folder, so nothing else on your Mac changes.

### How to undo it all afterwards

* pyusb: delete the program's folder (the `venv` folder inside it holds
  pyusb).
* libusb: only if you installed it for this test, `brew uninstall libusb`.
  If Homebrew says another package needs it, keep it.
* If macOS installed the command line developer tools for Python, they can
  stay (they are Apple's own and harmless).
* The program leaves one empty file, `chromiq-i1io-trace.lock`, in your
  temporary folder. It makes sure two copies never run at once; deleting it
  could defeat that, so the program leaves it. It takes no space, and macOS
  clears the temporary folder by itself.

---

## 3. Preparing the table

* **If the table was switched on since you last used i1Profiler: open
  i1Profiler once, wait until it shows the table, and quit it.**
* **Quit i1Profiler** (i1Profiler menu, Quit i1Profiler). The program refuses
  to start while it runs, because two programs must never talk to the table at
  the same time. X-Rite's background helpers (i1ProfilerTray, X-Rite Device
  Services) can keep running; you do not need to stop them, and please do not
  try to stop them by hand. If the program then says the table cannot be
  opened, nothing was sent: send us the log and stop there.
* The **arm must be at its resting place**, with the motors holding it, as
  i1Profiler leaves it.
* **Leave the i1Pro 2 seated in the arm's holder and connected**, exactly as
  when you use it with i1Profiler (every recording was made like that). The
  program never talks to it.
* **Take everything off the table**: no paper, no chart, nothing.
* Have the table's **power switch or plug** within reach, and look at the arm.

---

## 4. The real run

```
venv/bin/python3 i1io_trace.py --real
```

It first checks that pyusb and libusb are there, then explains the risks,
asks three short questions (power within reach, instrument seated, table
empty) and asks you to type this sentence:

```
I understand that this moves my table
```

Then it reads the table and goes through the steps above. Answer each question
by typing the whole word (`yes`, `no`, `stop`, `rests`, `gap`, ...) and
pressing Enter. Pressing Enter alone, or a single letter, never answers.

### How to stop

* Type `stop` at any question (at "Send step 1 now?" `no` works too).
* Press **Ctrl-C** at any time. After Ctrl-C has been noticed, the program
  never starts a movement. A movement that has already begun is not stopped by
  Ctrl-C: only the power switch or plug stops it.
* **Switch the table off or pull its power plug.** Always allowed, at any
  moment; it will most likely stop a movement that has begun. Pulling the USB
  cable alone does not do that: the table has its own power supply.

If the program stops and the arm is not at its resting place, the arm stays
where it is. To bring it home, open i1Profiler once and let it connect to the
table, then quit it. Please do not start this program again until i1Profiler
has brought the arm home.

If the program says the table **never reported that its movement had
finished**, please keep your hands away from the arm, switch the table off,
wait ten seconds and switch it on again before you open i1Profiler, and keep
your hands away when you switch it on as well (nobody knows yet whether the
table moves by itself then).

---

## 5. What to report

The program writes a log file into the folder, named
`i1io-trace-<date>-<time>.txt`. It holds every line sent and received, with
times, your answers, the macOS, Python, pyusb and libusb versions, and **no
serial number**. Please **read it before you post it**, then attach it to
issue #129 (the log file itself, not a copy of the Terminal window), together
with a few words:

* did the arm move at all, and how much;
* any sounds, and when;
* what you saw under the instrument holder;
* anything unexpected at all.

Thank you for trying it. A second small test, with a short movement, may
follow once your log is in.

---

## Licence

GPL-3.0-or-later, like ChromIQ itself (see `LICENSE`).
Source: https://github.com/itsab1989/ChromIQ (folder `tools/i1io_trace`).

*Written by Claude, the AI assistant working with Basti.*
