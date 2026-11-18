# Template: the "honest limits" part of the release notes

A driven instrument's first releases carry steps that nobody has tried on real hardware yet.
Say so, in the release notes (CHANGELOG.md), in the Beta switch's ⓘ and in the consent window,
in the same words. Never let one of them promise more than another, or more than the code does.

```markdown
### <Instrument>: driven by ChromIQ (Beta, off by default)

**What it does.** <One short paragraph: START on a chart made for the device measures it;
which device and instrument combinations; which run types.>

**How it was made.** The commands, speeds and timings were worked out from <N> owners'
recordings of <the maker's program and its version>, not from the maker's documentation. Only
lines seen in those recordings are sent, <and computed moves only in the recorded form, at
recorded speeds, inside our estimate of the measuring area>. Nothing is ever written into the
memory of the device or the instrument.

**What has been tried on a real device, and what has not.**
| part | tried on a real device? |
|---|---|
| <opening, homing, the recorded moves> | yes, on one owner's <device>, <date> |
| <reading patch by patch> | not yet: a first try |
| <strip reading> | not yet: a first try, off by default |

**What can go wrong, and the way out.** The power switch stops the device at once, always.
Stop in ChromIQ lets a move that has begun finish, then nothing more moves. <What a person does
if a move may still be waiting.>

**What we would like to hear.** <What to check, what to send (the session log, the maker's own
measurement of the same sheet), and where: issue #NNN.>
```

Rules for the words:

* "first try" for everything not yet seen working on a real device, until it has been;
* "our estimate" for any limit not taken from a recording or the maker's published figures;
* no "always safe", "all movements work", "before every move" unless a test proves exactly that;
* the same facts in every place the person can read them, changed together.
