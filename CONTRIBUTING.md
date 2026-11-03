# Contributing to ChromIQ

Thank you for helping. ChromIQ is a PyQt6 GUI for ArgyllCMS printer
profiling, licensed under the GPL-3.0 ([`LICENSE`](LICENSE)). Contributions are
welcome as bug reports, ideas, translations and pull requests.

## Before you start

- **Bugs and ideas**: use the issue forms (see
  [`.github/SUPPORT.md`](.github/SUPPORT.md)). For a larger change, open an
  issue first so we can agree on the shape before you write much code.
- **Read [`CLAUDE.md`](CLAUDE.md).** Despite the name, it is the project's
  rulebook for people and coding agents alike: setup, the test suite, the Qt
  crash rules, translations, and the binding design specifications in
  `docs/design/`. Some parts describe the maintainer's own machine; follow
  their intent, not their paths.
- Working with a coding agent? It should read [`AGENTS.md`](AGENTS.md) first.

## Adding a measuring instrument

Support for a new instrument is one of the most valuable contributions, and
one of the largest. Please read
**[`docs/adding_an_instrument.md`](docs/adding_an_instrument.md)** before you
begin. It covers what to bring (a working driver or connection and the device
in your hands), which existing integration to model yours on, the Preferences
> Beta option that keeps everyone else's ChromIQ unchanged, every place an
instrument has to be registered, and the mistakes earlier reviews found. A
prompt you can hand to your coding agent is in
[`docs/adding_an_instrument_agent_prompt.md`](docs/adding_an_instrument_agent_prompt.md).

The maintainers cannot test hardware they do not own, so your report of what
you tested on the device is part of the pull request.

## Pull requests

- One topic per pull request, based on the current `master`.
- Every behaviour change comes with a test that fails before it and passes
  after it. Tests use invented data, no network and no real device.
- Run the release gate before you ask for review, and read the exit code from
  pytest itself, not through a pipe:

  ```bash
  source .venv/bin/activate
  QT_QPA_PLATFORM=offscreen pytest --runslow -n auto -q > /tmp/chromiq-gate.txt 2>&1
  echo "exit=$?"
  ```

- User-facing text goes through `tr()` into all 13 language catalogues in
  `data/i18n/`, and new English text uses no em dash.
- New behaviour that a design specification covers is written there as
  "Awaiting confirmation"; a conflict with a specification is raised on GitHub
  first.
- Describe what changed, why, how you tested it (including in the real app,
  on screen), and anything you are unsure of.

Nothing here promises that a pull request will be merged, but following it
makes a review much shorter.
