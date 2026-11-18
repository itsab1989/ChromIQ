# SPDX-License-Identifier: GPL-3.0-or-later
"""The plug-in interface for one driven device, and the registry.

A plug-in knows four things about ONE device, and nothing else in the tools does:

1. which USB events are the device's (``assign_roles``), and which belong to an instrument
   that rides on it (an i1Pro 2 in a table's arm, say);
2. how the device's byte stream becomes LINES, in both directions (``lines``);
3. what a line means (``command_id``, ``describe``, ``answer_to``), and what must never be
   printed (``redact``: memory answers that hold a serial number, for example);
4. what the APP may send (``check``: the app's own allow-list, imported from the app, never a
   copy) and how the app would build a computed line (``rebuild``), so that a recorded line
   can be compared byte for byte with what ChromIQ would send.

To add a device, copy ``i1io2_table.py``, change what is device-specific, register it in
``PLUGINS`` below (or pass ``--plugin path/to/file.py:ClassName``), and add a test with
synthetic data like ``tests/test_recording_tools.py``.

Privacy rule for every plug-in: an instrument's MEASUREMENT data and the device's memory
contents are never printed. Print byte counts and request numbers instead.
"""
from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Line:
    """One line of the device's own protocol, as recorded."""
    t: float            # seconds from the first record: the line's first byte
    t_end: float        # when its last byte (the terminator) arrived
    who: str            # "host" (the program to the device) or "device"
    text: str           # the line without its terminator, already redacted where needed


@dataclass
class Verdict:
    """What the app's allow-list says about one host line."""
    allowed: bool
    label: str = ""                  # the allow-list's own name for it
    motion: bool = False             # a line that moves something
    reason: str = ""                 # why it is refused, when it is
    notes: list = field(default_factory=list)


class DevicePlugin:
    """Base class. Override what your device needs; the defaults do nothing harmful."""

    #: the name used with ``--plugin``
    name = "base"
    #: one line for ``--help`` and the reports
    description = ""

    def assign_roles(self, events) -> None:
        """Set ``ev["role"]`` to "device", "instrument" or None on every event."""
        for ev in events:
            ev["role"] = None

    def lines(self, events, t0: float) -> "list[Line]":
        """The device's lines in both directions, times relative to *t0*."""
        return []

    def command_id(self, line: Line) -> str:
        """A short id that pairs a host line with the device's answers to it."""
        return ""

    def answer_to(self, line: Line) -> "str | None":
        """For a device line that ENDS a command (a done or refused answer), its command id."""
        return None

    def describe(self, line: Line) -> str:
        """What the line means, in a few words, with its confidence where it is not certain."""
        return ""

    def describe_instrument(self, ev) -> "str | None":
        """A one-line description of an instrument event, WITHOUT its data (counts only)."""
        return None

    def check(self, line: Line) -> Verdict:
        """The app's own allow-list on one host line."""
        return Verdict(False, reason="this plug-in has no allow-list")

    def rebuild(self, line: Line) -> "str | None":
        """For a computed line, the line the app's own builder makes from the same numbers;
        None for a fixed line or one the app does not compute."""
        return None

    def is_routine(self, line: Line) -> bool:
        """A status poll or similar that ``--brief`` hides."""
        return False


def _registry():
    from . import i1io2_table
    return {i1io2_table.I1io2Table.name: i1io2_table.I1io2Table}


def plugin_names() -> "list[str]":
    return sorted(_registry())


def load_plugin(spec: str) -> DevicePlugin:
    """A registered name (``i1io2-table``), ``package.module:Class`` or ``path/file.py:Class``."""
    reg = _registry()
    if spec in reg:
        return reg[spec]()
    if ":" not in spec:
        raise SystemExit(f"unknown plug-in {spec!r}; registered: {', '.join(sorted(reg))}, "
                         "or give module:Class / path/file.py:Class")
    where, cls_name = spec.rsplit(":", 1)
    if where.endswith(".py"):
        path = Path(where).resolve()
        mod_spec = importlib.util.spec_from_file_location(path.stem, path)
        if mod_spec is None or mod_spec.loader is None:
            raise SystemExit(f"cannot load {where}")
        mod = importlib.util.module_from_spec(mod_spec)
        mod_spec.loader.exec_module(mod)
    else:
        mod = importlib.import_module(where)
    cls = getattr(mod, cls_name, None)
    if cls is None:
        raise SystemExit(f"{where} has no class {cls_name}")
    return cls()
