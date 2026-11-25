"""What a test FILE left in the worker's shared settings store, put back and named.

Every `AppSettings()` of a worker reads and writes ONE sandboxed ini (tests/conftest.py), so a
value one file leaves there is the starting point of every file after it. Three red gates of
4.3.62 and 4.3.64 were this: each victim passed alone, and which one fell depended on which files
xdist had given the worker before it (log_visible_lines=12 and a 12-line log; Manual's saved
instrument i1 and a Barbieri film frame restored as A2).

This compares the store after each file with the state before the first one, puts back what
changed, and names the file and the keys in the run summary. It REPORTS; it fails nothing. It
covers the store only: module globals and fields of objects that outlive a file are not seen.
"""
from __future__ import annotations

import time

#: written by the app or a conftest fixture on first use, the same for every file: putting them
#: back would only make them be written again
BENIGN = frozenset({"settings_schema", "log_privacy_salt", "update_check_blocked_until"})
_MISSING = object()


class SettingsStoreGuard:
    def __init__(self, ini: str):
        self.ini = str(ini)
        self.baseline: "dict | None" = None
        self.left: "dict[str, list[str]]" = {}
        self.seconds = 0.0
        self._file = None

    def _store(self):
        # PyQt's own class: core.settings.QSettings is the sandbox's stand-in. Every QSettings
        # on one path shares its contents in the process, unwritten values included
        from PyQt6.QtCore import QSettings
        return QSettings(self.ini, QSettings.Format.IniFormat)

    def _read(self, qs) -> dict:
        return {k: qs.value(k) for k in qs.allKeys() if k not in BENIGN}

    def file_begins(self, name: str) -> None:
        """Before the first test of *name* is set up. A file whose end was never seen (an
        interrupted teardown) is closed first."""
        if self._file == name:
            return
        t0 = time.perf_counter()
        if self._file is not None:
            self.file_ends()
        if self.baseline is None:
            self.baseline = self._read(self._store())
        self._file = name
        self.seconds += time.perf_counter() - t0

    def file_ends(self) -> "list[str]":
        """After the last test of the file was torn down, its module fixtures included."""
        name, self._file = self._file, None
        if name is None or self.baseline is None:
            return []
        t0 = time.perf_counter()
        qs = self._store()
        now = self._read(qs)
        changed = sorted(k for k in now.keys() | self.baseline.keys()
                         if not _same(now.get(k, _MISSING), self.baseline.get(k, _MISSING)))
        for k in changed:
            if k in self.baseline:
                qs.setValue(k, self.baseline[k])
            else:
                qs.remove(k)
        if changed:
            qs.sync()
            self.left[name] = sorted(set(self.left.get(name, [])) | set(changed))
        self.seconds += time.perf_counter() - t0
        return changed


def _same(a, b) -> bool:
    try:
        return type(a) is type(b) and bool(a == b)
    except Exception:      # noqa: BLE001 - a value that cannot be compared counts as changed
        return False


def summary_lines(left: "dict[str, list[str]]", seconds: "list[float]") -> "list[str]":
    if not left:
        return []
    out = [f"  {len(left)} test files left settings in their worker's shared store. Each was put "
           "back at the file's",
           "  end, so no later file saw it. Report only. "
           f"Cost: {max(seconds or [0.0]):.2f} s on the slowest worker."]
    for name in sorted(left):
        keys = left[name]
        shown = ", ".join(keys[:5]) + (f" and {len(keys) - 5} more" if len(keys) > 5 else "")
        out.append(f"  {name}: {shown}")
    return out
