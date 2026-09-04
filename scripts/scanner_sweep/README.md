# The sweep, so it never has to be improvised again

`run-sweep.sh` drives the **real** "Build profile with scanner or camera"
window on screen and records PASS / FAIL / UNTESTED for each function. It takes
about 12 minutes for the whole set on this machine.

```
./run-sweep.sh                 # everything
./run-sweep.sh J12 J24 J30     # just these
CHROMIQ_TREE=/tmp/mytree ./run-sweep.sh J30      # a patched checkout
```

Results land in `$WORK/out/results-<tag>.json` and a markdown table is rewritten
**after every single check**, so a killed run still leaves everything it got to.
Screenshots go to `../shots/`.

## What each check is

| id | what it drives |
|---|---|
| J01 | the window opens; both mode radios; the target list; which buttons are live with no scan |
| J02 | every entry in the Target type combo builds a grid |
| J03 | Try with a demo scan (single page) |
| J04 | Rotate 90° — four turns return to the start, w/h swap on the first |
| J05 | Reset view (zoom + pan) and Reset grid (re-seed) |
| J07 | Pop out / Dock back — parent, button text, Rotate disabled, placement kept |
| J08 | Sample area over its whole range: the marquee's drawn box against the box in the `.cht` scanin is actually handed |
| J09 | Use fiducial marks — `show_fiducials`, and the `-F` corners on both settings |
| J10 | the inert “Correct perspective” control is gone, and `-p` reaches no scanin call |
| J11 | Save a diagnostic image — `-dipon` |
| J12 | Auto align, then a second press to undo |
| J13 | Check alignment produces a verdict window |
| J14 | the whole build, end to end, from a demo scan |
| J15 | averaging: add / remove a scan, the method combo, per-shot placement |
| J16 | a multi-page set: a demo per page, per-page `.cht`, placement across a page round trip |
| J17 | Other… (.cht) |
| J18 | Save as Defaults / Restore defaults |
| J19 | closing the window mid-run |
| J20 | printer mode (scanner as the measuring device) |
| J21 | ChromIQ-chart mode on a real 3-page chart |
| J22 | Check alignment in ChromIQ-chart mode |
| J23 | the Sample-area cap must not leak from one chart or mode to the next |
| J24 | Knut's own Wolf Faust and LaserSoft scans, auto align + check alignment |
| J25 | the demo generator's framing against the marquee's seeded quad |
| J26 | the marquee's cell-geometry cache after **every** path that can move the grid |
| J27 | what the real build sends to scanin |
| J28 | demo → Auto align → Check alignment, over eight targets |
| J29 | crossed: fiducials × sample area × page |
| J30 | the untouched seed against the recogniser, on Knut's real scan |
| J31 | printer mode end to end — chart `.ti2` + a scanner ICC + three page scans |
| J32 | an EMPTY averaging slot: what the build actually reads |
| J33 | ChromIQ's warning sign in Light / Dark / Neutral |
| J34 | the two warning boxes in this window: sign, buttons, default, and the RETURN |
| J35 | every grid button pressed with no scan loaded |

`enumerate_controls.py` dumps every control of the live window (class, python
attribute, text, tooltip, range, items) per mode to `out/enumeration.json`. Run
it first when the window has changed — the table above is only as complete as
that dump.

## How each check would tell you it was wrong

Every check states its evidence in the `note` column rather than a bare PASS:
the numbers, the argv, the verdict sentence. A row that says PASS with an empty
note is a broken check, not a passing function. Three of them compare against
ground truth the app cannot fake:

* **J08** compares the marquee's drawn sample box with the box written into the
  `.cht` scanin is given — two independent code paths, same arithmetic.
* **J26** re-derives the marquee's cached cell geometry from the current grid
  and compares it with what is cached. A cache that is right by luck fails.
* **J28** takes the patch block's true corners from `demo_scan_layout`, the
  generator's OWN return value, not a copy of its arithmetic.


## Proving the sweep itself, not just the app

`test_the_sweep_is_runnable.py` is a pytest file that runs in a tenth of a
second and needs no window:

```
cd script
QT_QPA_PLATFORM=offscreen CHROMIQ_SETTINGS_FILE=/tmp/x.ini \
    pytest test_the_sweep_is_runnable.py -q
```

It asserts that the script is where `run-sweep.sh` looks for it and that the
runner is executable; that every check is registered and callable and there are
at least thirty of them; that **the table above names exactly the checks that
exist**, in both directions; that a check can actually record a FAIL and that
the evidence survives into the table; that the table is rewritten after every
single check, so a killed run keeps what it got to; and — the important one —
that `cache_state`, the instrument J26 uses on the marquee's new geometry cache,
**can see a stale cache**. It is shown one, by changing an input behind the
setter's back, and must answer STALE. An instrument that always says "coherent"
would have passed J26 with the cache broken.

It lives here rather than in `tests/` because the script does, and because it
should be run by whoever is about to re-run the sweep — not by the gate.
