# scripts/

Developer tools, on-screen drivers, probes and fixture builders. None of them is part of the app.
**The catalogue, by purpose, is [`docs/dev_tools_index.md`](../docs/dev_tools_index.md)**: find
the tool you need there before you write a new one. Its bottom half lists every file in this
folder with the first line of its docstring, and `python scripts/make_tools_index.py` rewrites
it (a test fails when it is out of date, so run it after adding a script).

## Two kinds of script

- **TOOL**: reusable and kept working (the drivers' harness `userdrive.py`, the photographing
  helpers in `onscreen_capture.py`, the parity checks, the byte-identity comparison, the
  recording tools, the planted-fault runner, the gate and disk tools).
- **example**: a one-off check from a past review or release round (`drive_*`, `adv*`, `probe_*`,
  many `make_*`), kept as a worked pattern. It may need adapting; some still carry paths of the
  maintainer's machine, and the catalogue says which.

## Safe to run for a stranger: the rules every new script here follows

1. **Settings are sandboxed first.** A script that starts the app builds a real `AppSettings`,
   which is the preferences store you work with every day. Set `CHROMIQ_SETTINGS_FILE` to a
   scratch `.ini` before you start any of them:

   ```bash
   export CHROMIQ_SETTINGS_FILE=/path/to/a/new/folder/settings.ini
   ```

   New drivers and examples refuse to start without it (a guard at the top), or set it
   themselves inside their own new output folder before anything is imported, as
   `scripts/userdrive.py` does.
2. **Output goes into a NEW folder the script is given**, and a script refuses a folder that
   already exists. Nothing is written beside your projects or into your home folder.
3. **Nothing is deleted outside a folder the script created itself.** The tools added for
   driven instruments (`planted_faults.py`, the recording tools, the proof driver template)
   delete nothing at all; they say how large their output is, and leave it to you.
4. **No print dialog, no real printer.** A driver never prints; one that must show the print
   path uses a capture queue (see `CLAUDE.md`).
5. **Nothing is posted anywhere** (no issue comments, no forum, no upload), and no device is
   opened: a driver puts a simulated device behind the app (for the i1iO 2 table,
   `tests/i1io_table/window_sim.py`).
6. **The keyboard stays yours.** A driver never raises or activates its window; it photographs
   the window by its id (`onscreen_capture.capture_window`) and gives focus back.
7. **Private data never goes in.** No serial numbers, recordings, readings of a real device,
   names or home paths in a script, its tests or its output meant for the repository.

## Running one

From the repository root, inside the project's `.venv`:

```bash
python scripts/<name>.py --help
```

Drivers need a display (macOS: Screen Recording allowed for your terminal), most need
ArgyllCMS (`/Applications/Argyll/bin` by default), and the test-only modules they import come
from `tests/`. The suite itself is run as `CLAUDE.md` describes ("Test").

## The tools for an instrument ChromIQ drives itself

| script | what it does |
|---|---|
| `recording_timeline.py` | a USB recording of the maker's program as a timeline, or one row per command (`--commands`) |
| `recording_vs_allowlist.py` | every recorded line against the app's allow-list, computed lines rebuilt byte for byte |
| `recordings/` | the recording reader, the plug-in interface (`recordings/plugins/`) and the i1iO 2 table's plug-in |
| `recordings/synthetic.py` | an invented recording to try the two tools on |
| `planted_faults.py` | plants faults in copies of the tree and reports which the tests caught |
| `driven_instrument_proof_driver.py` | template on-screen proof driver, runnable on the simulated i1iO 2 table |

The process they belong to is in `docs/adding_an_instrument.md`, section 12b.
