# A prompt for your coding agent: adding an instrument to ChromIQ

Copy everything between the two lines below into your coding agent (Codex,
Claude Code, Copilot, Cursor or another), and fill in the three blanks at the
top. The guide it points to is
[`docs/adding_an_instrument.md`](adding_an_instrument.md).

---

You are helping me add support for a measuring instrument to ChromIQ
(https://github.com/itsab1989/ChromIQ), a PyQt6 GUI for ArgyllCMS printer
profiling.

- Instrument: ______ (make and model)
- Connection: ______ (USB serial, USB HID, Bluetooth, Ethernet)
- What already works: ______ (for example "my Python driver reads one patch
  and returns a spectrum"; where it lives; its licence)

I have the instrument here. The ChromIQ maintainers do not, so anything only
the device can answer is my part: ask me, and I will test and report.

## Before you change anything

0. If there is no GitHub issue for this instrument yet, help me write one
   first (section 2 of the guide): a feature request titled "New instrument:
   <make and model>".
1. Start from the current `master` of itsab1989/ChromIQ on a new branch.
2. Read `docs/adding_an_instrument.md` in full, then `CLAUDE.md` in full. Both
   are binding. Parts of `CLAUDE.md` describe the maintainer's own machine and
   people (his Desktop folders, his display, his session hooks, Knut and
   Basti); follow their intent, not their paths: sandboxed settings, a real
   window for on-screen checks, no files left behind, no keyboard stealing,
   and "Knut or Basti must approve" means "the ChromIQ maintainers approve".
3. Decide which kind of instrument this is (section 3 of the guide) and which
   integration to model it on: the CR30 measure bridge or the FD-9's own path.
   Tell me which and why before you write code.
4. Read the design specifications the guide names for the areas you will
   touch, and the worked example's code and tests.
5. Write a plan that goes through the guide's registration checklist
   (section 5) row by row: for each row, say what you will change and in which
   file, or why the row does not apply. Show me the plan, and wait for my
   go-ahead before you write code.
6. Run the existing tests once inside the project's `.venv` for a green start:
   `QT_QPA_PLATFORM=offscreen pytest -n auto -q`.

## Rules you keep throughout

- **Beta option, off means no change.** Everything for this instrument sits
  behind one switch in Preferences > Beta, off by default, restart to apply.
  With it off, ChromIQ behaves exactly as before for every user. Prove it with
  the four nets of section 4 of the guide.
- **Do not contradict a specification on your own.** If what I need conflicts
  with a design specification in `docs/design/` or with the text of an
  existing message, stop, write up the conflict, and help me ask the
  maintainers on GitHub before you build it. New behaviour goes into the
  specifications as "⏳ Awaiting confirmation" with
  `**Confirmed by:** *nobody yet.*`.
- **Be careful with the device.** Send only the commands a measurement needs.
  No writes to device memory, settings, calibration or firmware. No address,
  length, flag or command number from user input or a file. No extra command
  "just to look", not even to read a version or reset a screen. If something
  seems to need a new command, stop and ask me, so we can ask the maintainers.
  Never send a print job to a real printer.
- **Every device wait has a timeout; every reply is length-checked** before
  it is used (section 9).
- **No new top-level scripts or research code in the bundle.** Ship only the
  driver code the app runs.
- **No device data in the repository.** Tests use invented values and
  synthetic data, and never open a network connection or a real port. Never
  commit readings, calibration bytes, scans, session folders or transcripts
  from my unit.
- **Text for people.** Every user-facing string, log lines included, is in
  `tr()`, friendly, complete, easy to understand and correct, with no em dash
  in English; it goes into all 13 translation catalogues. New measurement windows
  get an ID in §M-PROPOSED and in `workflow/measurement_messages.py`, word for
  word.
- **Qt rules.** No device I/O on the GUI thread; worker threads unparented,
  kept in a module list until finished, and made roomy with
  `core/thread_stack.py`; signals to bound methods, never self-capturing
  lambdas; never switch automatic garbage collection on.
- **Settings and paths.** Settings in `AppSettings` only. Paths through
  `Project` / `Run` / `Calibration`. A session data folder has a retention
  rule.
- **Tests.** Every behaviour change gets a test that fails before and passes
  after. Subprocesses get a `timeout=`. No modal `.exec()` in tests.

## Before you open the pull request

1. Run the language, em dash, message catalogue and specification tests, the
   everyday tier, and then the release gate exactly as section 12 of the guide
   shows. Read the exit code from pytest itself, not through a pipe, and do not
   edit files while the gate runs. If a test fails that your change cannot
   have caused, run it on unchanged `master` and report both results.
2. Help me check the real app in a real window, with the option on and off,
   with sandboxed settings and a scratch output folder (section 13). Do not
   move the keyboard focus while I am typing.
3. **Review your own diff in a separate pass.** Go through section 5 and
   section 15 of the guide row by row and write, for each row, done / not
   applicable (why) / open, as a table for the pull request description.
   Report what you found and fixed.
4. Draft the pull request description from section 14 of the guide, including
   what was and was not tested on the device, the new message IDs, the
   translations you are unsure of, the driver's commands, and the test counts.
   One topic per pull request.
