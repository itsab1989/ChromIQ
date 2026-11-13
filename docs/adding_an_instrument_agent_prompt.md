# A prompt for your coding agent: adding an instrument to ChromIQ

Copy everything between the two lines below into your coding agent (Codex,
Claude Code, Copilot, Cursor or another), and fill in the three blanks at the
top. It points to the guide,
[`docs/adding_an_instrument.md`](adding_an_instrument.md), and to its strict
companion, [`docs/adding_an_instrument_checklist.md`](adding_an_instrument_checklist.md).

---

You are helping me add support for a measuring instrument to ChromIQ
(https://github.com/itsab1989/ChromIQ), a PyQt6 GUI for ArgyllCMS printer
profiling.

- Instrument: ______ (make and model)
- Connection: ______ (USB serial, USB HID, Bluetooth, Ethernet)
- What already exists: ______ (for example "my Python driver reads one patch
  and returns a spectrum", or "recordings of the maker's program made with
  the ChromIQ probe"; where it lives; its licence)

I have the instrument here, or a tester who has. The ChromIQ maintainers do
not, so anything only the device can answer is my part: ask me, and I will
test and report.

## Before you change anything

0. If there is no GitHub issue for this instrument yet, help me write one
   first (section 3 of the guide): a feature request titled "New instrument:
   <make and model>".
1. Start from the current `master` of itsab1989/ChromIQ on a new branch.
2. Read `docs/adding_an_instrument.md`, `docs/adding_an_instrument_checklist.md`
   and `CLAUDE.md` in full. All three are binding. Parts of `CLAUDE.md`
   describe the maintainer's own machine and people (his Desktop folders, his
   display, his session hooks, Knut and Basti); follow their intent, not their
   paths: sandboxed settings, a real window for on-screen checks, no files
   left behind, no keyboard stealing, and "Knut or Basti must approve" means
   "the ChromIQ maintainers approve".
3. Collect the facts (section 5 of the guide): each with its source and how
   sure it is. Decide which kind of instrument this is (section 4 of the
   guide) and tell me which route and why before you write code.
4. Read the design specifications the checklist names for the areas you will
   touch.
5. Write a plan that goes through every stage of the checklist, item by item:
   for each, say what you will change and in which file, or why it does not
   apply. Include the options table (section 7 of the guide) and the run
   types (section 8 of the guide). Have the plan challenged by a separate
   session that did not write it, fold in its findings, show me the plan, and
   wait for my go-ahead.
6. Run the existing tests once inside the project's `.venv` for a green start:
   `QT_QPA_PLATFORM=offscreen pytest -n auto -q`.

## Rules you keep throughout

- **Options stay open.** Safe defaults; an option is unavailable only when it
  has no meaning for this instrument or the chart cannot be built with it.
  Everything that works is saved as defaults, in presets, per target and in
  the chart's record, proven by one table-driven test.
- **Every run type** (Profiling, Verification, Calibration) in Guided and
  Manual, or a visible window saying what is not available yet.
- **Beta switch, off means no change.** Everything for this instrument sits
  behind one switch in Preferences > Beta, off by default, with a consent
  window. Prove "off" with the four nets and the file comparison of the
  checklist.
- **Do not contradict a specification on your own.** Raise a conflict with
  the maintainers on GitHub. New behaviour goes into the specifications as
  "⏳ Awaiting confirmation" with `**Confirmed by:** *nobody yet.*`.
- **Careful with the device** (section 12 of the guide): only commands that
  are understood, in the situations they were seen in; no writes to the
  device's memory, settings, calibration or firmware; no movement on a guess;
  no command "just to look"; a simulator first. If something seems to need a
  new command, stop and ask me.
- **Do not change another instrument's code as a side effect.** Report what
  you notice; other instruments only need to stay unchanged.
- **Never send a print job to a real printer.**
- **No device data in the repository.** Invented values only.
- **Text for people**, in `tr()`, in all 13 languages with a second
  translation pass, no em dash in English; new windows in §M-PROPOSED first.
- **Settings in `AppSettings`, paths through `Project` / `Run` / `Calibration`.**

## Before you open the pull request

1. Run the checks and the gate exactly as stage 10 of the checklist shows.
   Read the exit code from pytest itself, not through a pipe, and do not edit
   files while the gate runs.
2. Help me check the real app in a real window, switch on and off, with
   sandboxed settings and a scratch output folder. Do not move the keyboard
   focus while I am typing.
3. Have the result reviewed by a separate session that did not build it, given
   the diff rather than your conclusions; fix and repeat until it finds
   nothing that matters.
4. Mark every checklist item done / not applicable (why) / open, and draft the
   pull request description from section 15 of the guide. One topic per pull
   request.
