# Copilot instructions for ChromIQ

- The project's general rules are in [`CLAUDE.md`](../CLAUDE.md) and apply to
  every coding agent. A short summary is in [`AGENTS.md`](../AGENTS.md).
- **Adding or changing a measuring instrument**: read
  [`docs/adding_an_instrument.md`](../docs/adding_an_instrument.md) in full
  first and follow its registration checklist. New instruments go behind a
  Preferences > Beta option, and with it off ChromIQ behaves exactly as before.
- User-facing text goes through `tr()` into all 13 translation catalogues, with no
  em dash in new English text.
- The design specifications in `docs/design/` are binding; raise a conflict
  with the maintainers on GitHub instead of changing it in code.
- Tests use invented data, no network and no real device.
