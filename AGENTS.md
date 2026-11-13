# AGENTS.md

Instructions for coding agents working on ChromIQ (a PyQt6 GUI for ArgyllCMS
printer profiling).

## Read first

- **[`CLAUDE.md`](CLAUDE.md)** holds the project's general rules: setup, the
  test suite and its release gate, the Qt crash rules, translations, the
  binding design specifications and on-screen checks. They apply to every
  agent, not only Claude. Some parts describe the maintainer's own machine
  and people (his Desktop folders, his display, his session hooks, Knut and
  Basti): follow their intent, not their paths, and read "Knut or Basti must
  approve" as "the ChromIQ maintainers must approve".
- **Adding or changing a measuring instrument?** Read
  **[`docs/adding_an_instrument.md`](docs/adding_an_instrument.md)** in full
  before you change anything, then work through
  **[`docs/adding_an_instrument_checklist.md`](docs/adding_an_instrument_checklist.md)**
  stage by stage.
  Open a feature request issue for the instrument first, show the plan and
  wait for a go-ahead before you write code.
  A ready-made prompt is in
  [`docs/adding_an_instrument_agent_prompt.md`](docs/adding_an_instrument_agent_prompt.md).
- Contributing in general: [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Key rules

- A new instrument goes behind a Preferences > Beta option, off by default,
  and with it off ChromIQ behaves exactly as before.
- The specifications in `docs/design/` are binding. A conflict with one is
  raised with the maintainers on GitHub, not fixed in passing; new behaviour is
  written as "Awaiting confirmation".
- Every user-facing string goes through `tr()` into all 13 translation
  catalogues, and new English text uses no em dash.
- Settings live in `AppSettings` (`core/settings.py`); paths go through
  `Project` / `Run` / `Calibration` (`core/file_manager.py`).
- Never send a device a command it does not need, never write to its memory,
  settings or firmware, and never commit data read from a real device.
- Tests use invented data, no network and no real device. Run the gate with
  `QT_QPA_PLATFORM=offscreen pytest --runslow -n auto -q > /tmp/chromiq-gate.txt 2>&1; echo "exit=$?"`
  and read the exit code from pytest, not through a pipe. On Windows
  PowerShell:
  `$env:QT_QPA_PLATFORM='offscreen'; pytest --runslow -n auto -q > $env:TEMP\chromiq-gate.txt 2>&1; echo "exit=$LASTEXITCODE"`.
  A change to the profile engine needs the FULL gate, the same command with
  `--runengine` added; `python scripts/gate_tier.py` says which one.
- One topic per pull request, and say what was and was not tested on real
  hardware.
