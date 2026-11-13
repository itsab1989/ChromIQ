# ChromIQ i1iO test program (first table test)

This is a very small test program for the **X-Rite i1iO 2** scanning table
with an **i1Pro 2**. It was written for ChromIQ issue #129, from the USB
recordings a table owner made with i1Profiler. It is the first time anything
other than X-Rite's software talks to the table, so it does as little as
possible: it checks that the table answers, moves the arm a short way in a
straight line and sends it back. **It never measures.**

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
   moves very little or not at all).
3. **Step 2:** moves the arm about **25 mm** (1 inch) straight towards the
   front of the table.
4. **Step 3:** moves it about **95 mm** further in the same straight line, so
   it stops about 12 cm from its resting place.
5. **Step 4:** sends the arm back to its resting place.

Before each of the four steps it shows you the exact line it is about to send
and what you should see, and it waits until you type `yes`. After each step it
asks you whether the arm did what was described.

It can send only **seven different lines** to the table, and every one of them
is a line i1Profiler itself sent to the tester's table in the recordings, byte
for byte:

| Line | What it does |
|---|---|
| `;s022` | asks for the table's status (nothing moves) |
| `;a133` | asks the table who it is (nothing moves) |
| `;f42b` | asks whether the motors hold the arm (nothing moves) |
| `;p025` | asks where the arm is (nothing moves) |
| `;i12b` | sends the arm to its resting place |
| `;m0044e00fa012c0e` | moves the arm to the place 25 mm in front of its resting place |
| `;m0044e04b200c838` | moves the arm to the place 12 cm in front of its resting place |

`python3 i1io_trace.py --plan` prints the whole sequence, in order.

**It never** sends anything that lowers or lifts the measuring head, never
measures, never talks to the i1Pro 2 at all, and never reads or writes the
table's memory. It never reads the table's serial number.

**If anything is not as expected** (no answer, a strange answer, an error, the
arm not where it was sent, the cable gone) the program stops and sends
**nothing more at all**. It does not try to tidy up or bring the arm home by
itself; the arm simply stays where it is.

---

## What could go wrong

In plain words: the arm could bump into something left on the table, or into a
hand. The table could do something the recordings never showed. In the worst
case the mechanism could be strained. That is why:

* the table must be **completely empty** (no paper, no chart, nothing on it);
* every movement waits for you;
* the table's **power switch or power plug** should be within reach.

**Switching the table off or pulling its power plug is always allowed**, at
any moment, and it stops the motors. Pulling the USB cable alone does not stop
a movement that has already started.

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

Unpack the zip, then open the Terminal in that folder (or type `cd ` and drag
the folder onto the Terminal window, then press Enter).

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
venv/bin/python3 -m pip install pyusb
```

(The first line installs libusb only if it is not there yet. If it says it is
already installed, please note that, so you know not to remove it later.)

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
  like that, so this is the situation the program's lines are known to work
  in. The program never talks to the i1Pro 2.
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

Then it reads the table, tells you what it found, and goes through the four
steps. Answer each question by typing the whole word (`yes`, `no`, `stop`,
`gap`, ...) and pressing Enter. Pressing Enter alone never answers.

After step 2 it asks you to look at the bottom of the instrument holder,
where the round measuring opening is, and to say whether it touches the table
or whether there is a gap. Please look closely: this is one of the things we
most want to know. If it touches, or you are not sure, the program stops there.

At the end it asks two short questions about sounds and anything that
surprised you.

### How to stop

* Type `stop` (or `no`) at any question.
* Press **Ctrl-C** at any time. If a movement is under way, the table finishes
  that movement and then the program stops; it never cuts a movement in half.
* **Switch the table off or pull its power plug.** Always allowed.

If the program stops in the middle, the arm stays where it is. To bring it
home, open i1Profiler once and let it connect to the table, then quit it.

---

## 5. What to report

The program writes a log file into the folder, named
`i1io-trace-<date>-<time>.txt`. It holds every line sent and received, with
times, your answers, the macOS and Python versions, and **no serial number**.
Please **read it before you post it**, then attach it to issue #129 together
with a few words:

* what the arm did at each step (did it move as described?);
* any sounds (grinding, knocking, clicking, a long buzz) and at which step;
* what you saw under the instrument holder after step 2;
* anything unexpected at all.

Thank you for trying it.

---

## Licence

GPL-3.0-or-later, like ChromIQ itself (see `LICENSE`).
Source: https://github.com/itsab1989/ChromIQ (folder `tools/i1io_trace`).

*Written by Claude, the AI assistant working with Basti.*
