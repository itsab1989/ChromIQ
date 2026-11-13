"""The i1Pro 2 lights (Preferences > Beta): the "lights may still be on" marker.

A precaution, asked for by the owner on 2026-11-13 ("is this needed? then
yes"). ArgyllCMS's own notes in i1pro_imp.c say a light pattern that is still
running can disturb the instrument's EEPROM read at start-up, and a helper
that crashed or was killed while the white light was on cannot switch it off.
So, while the option is on:

* the moment a session's helper reports that the white light is on
  (``{"event":"lights","active":true}``), ChromIQ writes a small marker;
* a clean ending removes it: the helper's ``{"event":"lights","state":"off"}``,
  or a normal exit of the helper, whose close switches the lights off first;
* a crash, a kill that the helper did not answer, a stuck close or a failed
  light request leaves it, because the lights may then still be on;
* at the next Start of a chart for the i1Pro family, a marker still there
  shows one window (M-I1PRO2-LIGHTS-LEFT-ON) asking to unplug and replug the
  instrument before anything is connected. Continue removes the marker;
  Cancel keeps it and does not start.

**With the option off, nothing here touches the disk**: every entry point
takes the option and returns at once when it is off.

**Where it lives.** ChromIQ's own settings folder, beside the presets, as
``i1pro2-lights-on.json`` (the ``printer_memory`` rule). With
``CHROMIQ_SETTINGS_FILE`` set it lives beside that file instead, so a driver
or a test never reaches the real one; without it, ``CHROMIQ_PRESETS_DIR``
moves it with the presets. Never in a project folder.

**What it holds**: the instrument type and the time the light went on. Nothing
else, and nothing personal. A marker for another instrument type, or one that
cannot be read, never shows the window.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from core.logger import get_logger

log = get_logger(__name__)

FILE_NAME = "i1pro2-lights-on.json"
#: The only instrument type a marker is ever written for, and the only one
#: that can show the window.
INSTRUMENT = "i1pro2"
#: The setting that is the option (core/settings.py DEFAULTS).
OPTION_KEY = "i1pro2_lights_beta"
#: The chart family the window is asked for (data/patch_db.instrument_family_of):
#: an i1Pro 2 reads charts laid out for the i1Pro family. Before anything is
#: connected, the chart is all ChromIQ knows about the instrument.
CHART_FAMILY = "i1"


def marker_path() -> Path:
    """Where the marker lives (see the module docstring)."""
    from core.settings import SETTINGS_FILE_ENV
    sandbox = os.environ.get(SETTINGS_FILE_ENV, "").strip()
    if sandbox:
        p = Path(sandbox)
        return p.with_name(p.stem + "." + FILE_NAME)
    from core.platform_paths import presets_dir
    return presets_dir().parent / FILE_NAME


def option_on(settings) -> bool:
    """Whether Preferences > Beta has the lights option on."""
    try:
        return bool(settings.get(OPTION_KEY, False)) if settings is not None \
            else False
    except Exception:      # noqa: BLE001 - never block a Start on this
        return False


def note_white_on(option: bool) -> None:
    """The white light of this session is on: write the marker."""
    if not option:
        return
    path = marker_path()
    data = {"instrument": INSTRUMENT,
            "since": time.strftime("%Y-%m-%dT%H:%M:%S")}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, path)
        log.info("i1Pro 2 lights: marker written (%s)", path)
    except OSError as exc:
        log.warning("i1Pro 2 lights: marker %s not written (%s)", path, exc)


def note_lights_off(option: bool) -> None:
    """The lights were switched off cleanly: remove the marker."""
    if not option:
        return
    clear()


def clear() -> None:
    """Remove the marker. Only ever called from a path the option opened
    (a session whose lights were in use, or the Start window)."""
    path = marker_path()
    try:
        path.unlink()
        log.info("i1Pro 2 lights: marker removed (%s)", path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        log.warning("i1Pro 2 lights: marker %s not removed (%s)", path, exc)


def is_lights_off_line(line: str) -> bool:
    """Whether *line* is the helper's ``{"event":"lights","state":"off"}``."""
    text = (line or "").strip()
    if not text.startswith("{"):
        return False
    try:
        ev = json.loads(text)
    except ValueError:
        return False
    return (isinstance(ev, dict) and ev.get("event") == "lights"
            and ev.get("state") == "off")


def left_on(option: bool, chart_family: "str | None") -> bool:
    """Should Start show M-I1PRO2-LIGHTS-LEFT-ON?

    Only with the option on, only for a chart of the i1Pro family (so it never
    stands in front of another instrument), and only for a marker this module
    wrote for an i1Pro 2. Nothing is read when the option is off or the chart
    is for another instrument."""
    if not option or chart_family != CHART_FAMILY:
        return False
    path = marker_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False
    except (OSError, ValueError) as exc:
        log.warning("i1Pro 2 lights: marker %s unreadable (%s); ignored",
                    path, exc)
        return False
    return isinstance(data, dict) and data.get("instrument") == INSTRUMENT
