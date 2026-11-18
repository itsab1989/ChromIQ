# Template: one step of a tester program, as the volunteer reads it

A tester program is a small console program a volunteer runs on their own device before any of
it goes into the app (docs/adding_an_instrument.md, section 12b, step 3). Each step is shown
like this before it runs, and nothing happens until the volunteer types the whole word `yes`.
The public example is the i1iO session program on the branch
[`tester/i1io-session-0.6.0`](https://github.com/itsab1989/ChromIQ/tree/tester/i1io-session-0.6.0/tools/i1io_session).

```text
Step <N>: <what happens, in one line a person understands>

<What moves, how far, and how long it took in the maker's program: "The arm drives straight
out by 150 mm in about 1.7 s, then back home (about 2 to 3 s).">

Exactly as recorded: <what is byte for byte as the maker's program sent it>.
Not exactly as recorded: <every way this step goes beyond a recording: a different order, a
place nearer than any recorded one, a check added between two moves>.
Depends on: <the steps that must have run cleanly first in this sitting>.

<lines> lines, <movements> movements. Our risk rating: <low / medium / a first try>.
To stop the device at once, switch it off at its power switch. Ctrl-C stops the program from
sending anything more, but a movement that has begun is not stopped by Ctrl-C.

Type yes to run it, skip to leave it out, or end to finish the sitting:
```

After the step, ask, one at a time and in plain words:

```text
Did it do what was described?  (as described / something was different / not sure)
What did you see, hear or feel? (optional, one or two lines)
```

What the program must do around every step:

* **A true state afterwards.** Read the device's position (or state) after the step and say
  only what that reading shows. "At its resting place" only when it was read there.
* **A way out after every step**: the next offer, skip, end, and the power switch. A step that
  failed cleanly (nothing left waiting, the position read) ends only that step; anything not
  clean (a move whose end is not known, an answer never seen before, Ctrl-C) ends the sitting,
  and nothing more is sent.
* **A switch-off first** whenever a move may still be waiting: the first words are "switch the
  device off now", a marker file is left so the next start says it again, and no text suggests
  anything that could set the move off.
* **A log that can be analysed**: every line sent and received with its time (to the
  millisecond), every position the device reported, how long each movement took, the
  volunteer's answers and notes, the program's version and the allow-list it ran with. No
  serial number, nothing from the device's memory, no user name or home folder.
* **One results file** to send back, and a request for the maker's own measurement of the
  same sheet, so the two can be compared.
