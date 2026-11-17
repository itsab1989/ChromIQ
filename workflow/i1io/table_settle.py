# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""The app's side of the table package's files (outside ``workflow/i1io/table/``, which imports
no app module): where the app-level pending markers live, and the settle hook below.

Before the Measure tab writes a run's measurement by any other way than the table (a hand
measurement, an import), the run's table sessions are settled (review 9, NOTE on S-4): a session
whose Save was cut off after the run's file was written gets its result recorded, so it stays
"saved" after the hand write changes the file.

Outside ``workflow/i1io/table/`` on purpose: a run without table sessions (every run while the
i1iO Beta is off) costs one ``is_dir()`` and imports nothing of the table package.
"""
from __future__ import annotations

from pathlib import Path


def settle_table_sessions_before_a_hand_write(run) -> "list[str]":
    """The stamps settled ([] when the run has no table sessions). Never raises: a run that
    cannot be read stays as it is."""
    try:
        if run is None or not Path(run.i1io_table_dir).is_dir():
            return []
        from workflow.i1io.table import session_end as se
        return se.settle_filed_sessions(run)
    except Exception:      # noqa: BLE001 - a precaution, never a blocker of a measurement
        return []


#: review 9, NOTE: the app-level "a strip move may still wait" markers; the job is told where
APP_MARKER_PREFIX = "i1io-table-move-may-be-pending-"


def app_marker_place() -> "tuple[Path, str]":
    """(folder, file-name prefix) of the app-level pending markers: ChromIQ's own settings
    folder, as the i1Pro 2 lights marker (``core/i1pro2_lights_marker.py``): beside
    ``CHROMIQ_SETTINGS_FILE`` when it is set (a driver or a test never reaches the real one),
    else beside the presets folder. Never a project folder."""
    import os
    from core.settings import SETTINGS_FILE_ENV
    sandbox = os.environ.get(SETTINGS_FILE_ENV, "").strip()
    if sandbox:
        p = Path(sandbox)
        return p.parent, p.stem + "." + APP_MARKER_PREFIX
    from core.platform_paths import presets_dir
    return presets_dir().parent, APP_MARKER_PREFIX
