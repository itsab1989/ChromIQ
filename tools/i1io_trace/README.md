# ChromIQ i1iO test program (first table test)

This is a very small test program for the **X-Rite i1iO 2** scanning table
with an **i1Pro 2**. It was written for ChromIQ issue #129, from the USB
recordings a table owner made with i1Profiler. It is the first time anything
other than X-Rite's software talks to the table, so it does as little as
possible: it checks that the table answers, moves the arm about 12 cm towards
the front of the table and sends it back. **It never measures.**

It is not part of the ChromIQ app, and it does not need ChromIQ.

Nothing here is promised. Whether you try it is entirely your choice, and you
can stop at every step.

---

## What it does, and what it never does

With `--real` the program does exactly this, and nothing else:

1. **Reads** the table's identity, its status, its position and whether the
   motors hold the arm. Nothing moves. If the table is not exactly the model
   the recordings came from, or the arm is not at its resting place at the
   back of the table, or the motors do not hold it, the program stops here.
2. **Step 1:** sends the arm to its resting place (it is already there, so it
   moves very little or not at all). This is what i1Profiler does when it
   connects to the table.
3. **Step 2:** moves the arm about **25 mm** (1 inch) straight towards the
   front of the table.
4. **Step 3:** moves it about **95 mm** further towards the front, and about
   4 mm sideways, so it stops about 12 cm from its resting place.
5. **Step 4:** moves it about **4 mm** sideways.
6. **Step 5:** sends the arm back to its resting place.

Steps 3, 4 and 5 send the same three lines, in the same order, with which
i1Profiler brought the arm home when it started up in the first recording.
One difference: i1Profiler sent the step 3 line with the arm about 7 mm
further out and 4 mm to the side, so on the tester's table it made a straight
88 mm move, while here the same line makes a 95 mm move with a 4 mm sideways
part. It ends at the same place.

Before each of the five steps it shows you the exact line it is about to send
and what you should see, and it waits until you type `yes`. After each step it
asks you whether the arm did what was described.

It can send only **eight different lines** to the table, and every one of
them is a line i1Profiler itself sent to the tester's table in the
recordings, byte for byte:

| Line | What it does |
|---|---|
| `;a133` | asks the table who it is (nothing moves) |
| `;s022` | asks for the table's status (nothing moves) |
| `;f42b` | asks whether the motors hold the arm (nothing moves) |
| `;p025` | asks where the arm is (nothing moves) |
| `;i12b` | sends the arm to its resting place |
| `;m0044e00fa012c0e` | moves the arm to the place 25 mm in front of its resting place |
| `;m0042204b200c86d` | moves the arm to the place 12 cm in front of its resting place, 4 mm to the side |
| `;m0044e04b200c838` | moves the arm to the place 12 cm in front of its resting place |

`python3 i1io_trace.py --plan` prints the whole sequence, in order.

**It never** sends a command of its own to lower or lift the measuring head,
never measures, never talks to the i1Pro 2 at all, and never reads or writes
the table's memory. It never reads the table's serial number. (The table
itself may lower or lift the head when the arm leaves or reaches its resting
place; nobody knows that yet, which is why the program asks you to look.)

**If anything is not as expected** (no answer, a strange answer, an error, the
arm not where it was sent, the cable gone) the program stops and sends
**nothing more at all**. It does not try to tidy up or bring the arm home by
itself; the arm simply stays where it is.

---

## What could go wrong

In plain words: the arm could bump into something left on the table, or into a
hand. The table could do something the recordings never showed; nobody has
ever seen how it reacts to an obstacle or an error. In the worst case the
mechanism could be strained. That is why:

* the table must be **completely empty** (no paper, no chart, nothing on it);
* every movement waits for you;
* the table's **power switch or power plug** should be within reach.

**Switching the table off or pulling its power plug is always allowed**, at
any moment, and it will most likely stop the motors at once. Pulling the USB
cable alone most likely does not stop a movement that has already started,
because the table has its own power supply.

---

## Before you start

You need a Mac, the i1iO 2 with its i1Pro 2, and Python 3.

Check Python in the Terminal app:

```
python3 --version
```

If macOS offers to install the "command line developer tools", that is
Apple's own package and includes Python; you can accept it. Python from
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
receive, so you can see exactly what will happen. It writes a log file
ending in `-simulated.txt`.

---

## 2. What to install for the real table

The real run needs two things: the **libusb** library (from Homebrew) and the
Python package **pyusb**. The commands below put pyusb into a small folder
called `venv` inside the program's folder, so nothing else on your Mac
changes.

```
brew list libusb || brew install libusb
python3 -m venv venv
venv/bin/python3 -m pip install pyusb==1.2.1
```

(The first line installs libusb only if it is not there yet. If it prints a
list of files instead, libusb was already installed: please note that, so you
know not to remove it later.)

### How to undo the installs afterwards

* pyusb: delete the program's folder (the `venv` folder inside it holds
  pyusb). Nothing else was changed.
* libusb: only if you installed it for this test, `brew uninstall libusb`.
  If Homebrew says another package needs it, keep it.

---

## 3. Preparing the table

* **Quit i1Profiler.** The program refuses to start while it runs, because two
  programs must never talk to the table at the same time.
* The **arm must be at its resting place** at the back of the table, with the
  motors holding it, as i1Profiler leaves it. If it is not, open i1Profiler
  once, let it connect to the table (it sends the arm home by itself), then
  quit i1Profiler.
* **Leave the i1Pro 2 seated in the arm's holder and connected**, exactly as
  when you use it with i1Profiler. Every movement in the recordings was made
  like that, and the table may sense the instrument, so this is the situation
  the program's lines are known to work in. The program never talks to the
  i1Pro 2.
* **Take everything off the table**: no paper, no chart, nothing.
* Have the table's **power switch or plug** within reach.
* Stand where you can see the arm.

---

## 4. The real run

```
venv/bin/python3 i1io_trace.py --real
```

It explains the risks, asks three short questions (power within reach,
instrument seated, table empty) and then asks you to type this sentence:

```
I understand that this moves my table
```

Then it reads the table, tells you what it found, and goes through the five
steps. Answer each question by typing the whole word (`yes`, `no`, `stop`,
`gap`, ...) and pressing Enter. Pressing Enter alone, or a single letter, never
answers.

Two times it asks you to look at the bottom of the instrument holder, where
the round measuring opening is: after step 1, at the resting place (does it
rest on the white tile, or is there a gap?), and after step 2 (does it touch
the table, or is there a gap?). Please look closely: this is one of the things
we most want to know. If it touches the table after step 2, or you are not
sure, the program stops there.

At the end it asks two short questions about sounds and anything that
surprised you.

### How to stop

* Type `stop` at any question (at "Send step ... now?" `no` works too).
* Press **Ctrl-C** at any time. If a movement is under way, the table finishes
  that movement and the program checks where the arm arrived, then stops; it
  never sends a movement after you pressed Ctrl-C.
* **Switch the table off or pull its power plug.** Always allowed.

If the program stops in the middle, the arm stays where it is. To bring it
home, open i1Profiler once and let it connect to the table, then quit it.
Please do not start this program again until i1Profiler has brought the arm
home.

If the program says the table **never reported that its last movement had
finished**, please keep your hands away from the arm, switch the table off,
wait ten seconds and switch it on again before you open i1Profiler, and keep
your hands away when you switch it on as well (nobody knows yet whether the
table moves by itself then). That way a movement the table may still be
waiting to make cannot start later.

---

## 5. What to report

The program writes a log file into the folder, named
`i1io-trace-<date>-<time>.txt`. It holds every line sent and received, with
times, your answers, the macOS and Python versions, and **no serial number**.
Please **read it before you post it**, then attach it to issue #129 (the log
file itself, not a copy of the Terminal window), together with a few words:

* what the arm did at each step (did it move as described?);
* any sounds (grinding, knocking, clicking, a long buzz) and at which step;
* what you saw under the instrument holder after step 1 and after step 2;
* anything unexpected at all.

Thank you for trying it.

---

## Licence

GPL-3.0-or-later, like ChromIQ itself (see `LICENSE`).
Source: https://github.com/itsab1989/ChromIQ (folder `tools/i1io_trace`).

*Written by Claude, the AI assistant working with Basti.*
