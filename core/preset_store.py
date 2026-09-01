"""Filesystem-backed preset store with one .json file per preset.

Each manual-module tab gets its own subfolder under presets_dir() so
users can browse, copy and share presets with a normal file manager.

On first read for a given tab the store migrates any presets that were
previously held under the legacy QSettings key (binary plist on macOS),
writing them out as plain .json files.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any

from core.logger import get_logger
from core.name_order import sort_names
from core.platform_paths import presets_dir

log = get_logger(__name__)

CHROMIQ_PRESET_VERSION = 1

# Tab id -> human-readable folder name (matches the tab labels in the UI).
TAB_FOLDERS: dict[str, str] = {
    "create_chart":  "Create Chart",
    "measure":       "Measure",
    "build_profile": "Build Profile",
    "check_refine":  "Check & Refine",
    "chart_layout":  "Chart Layout",
}

# QSettings keys previously used to hold each tab's preset dict. Read once
# on first load to migrate; kept as a tombstone after migration.
LEGACY_KEYS: dict[str, str] = {
    "create_chart":  "manual_presets",
    "measure":       "manual2_measure_presets",
    "build_profile": "manual2_profile_presets",
    "check_refine":  "manual2_check_presets",
}

# Layout-engine presets (issue #93) have no legacy QSettings key — they were
# file-based from the start.


def tab_dir(tab: str) -> Path:
    """Directory holding the preset .json files for one tab."""
    return presets_dir() / TAB_FOLDERS[tab]


def _sanitize(name: str) -> str:
    """Return a filesystem-safe filename stem derived from `name`."""
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip()
    return safe or "Untitled"


def sidecar_path(tab: str, name: str, suffix: str) -> Path:
    """Path to a non-JSON file bundled alongside a preset (e.g. its .ti1).

    `suffix` includes the leading dot (".ti1"). Uses the same filename stem
    as the preset's .json so the pair travels together when shared.
    """
    return tab_dir(tab) / (_sanitize(name) + suffix)


def load_presets(tab: str, settings: Any = None) -> dict[str, Any]:
    """Return ``{name: payload_dict}`` for `tab`.

    On first call for a tab (when the subfolder doesn't yet exist) the
    legacy QSettings preset dict, if any, is migrated to disk before the
    folder is scanned.
    """
    d = tab_dir(tab)
    if not d.exists():
        d.mkdir(parents=True, exist_ok=True)
        if settings is not None:
            _migrate_from_settings(tab, settings)
    out: dict[str, Any] = {}
    for p in sorted(d.glob("*.json")):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("preset_store: skipping malformed %s (%s)", p, exc)
            continue
        if not isinstance(doc, dict):
            continue
        name = str(doc.get("name") or p.stem)
        data = doc.get("data", {})
        if isinstance(data, dict):
            out[name] = data
    # ORDERED BY THE NAME THE PERSON READS. The scan above walks the folder in
    # `sorted(glob(...))` order, which is the SANITISED FILE name compared byte
    # by byte — so the combos showed "Wide gamut, boost, check" (capitals
    # first, two alphabets) and ordered them by a name that is not the one on
    # screen. One rule, on the displayed name: core.name_order.
    return {name: out[name] for name in sort_names(out)}


def save_presets(tab: str, presets: dict[str, Any]) -> None:
    """Rewrite `tab`'s folder so its .json files exactly mirror `presets`.

    Files for presets no longer present in the dict are removed, so this
    one call cleanly handles add, rename and delete.
    """
    d = tab_dir(tab)
    d.mkdir(parents=True, exist_ok=True)
    wanted: set[str] = set()
    for name, payload in presets.items():
        fname = _sanitize(name) + ".json"
        wanted.add(fname)
        doc = {
            "chromiq_preset_version": CHROMIQ_PRESET_VERSION,
            "tab": tab,
            "name": name,
            "data": payload,
        }
        try:
            (d / fname).write_text(
                json.dumps(doc, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            log.warning("preset_store: failed to write %s (%s)", d / fname, exc)
    for p in d.glob("*.json"):
        if p.name not in wanted:
            try:
                p.unlink()
            except OSError as exc:
                log.warning("preset_store: failed to remove %s (%s)", p, exc)


def _migrate_from_settings(tab: str, settings: Any) -> None:
    """One-shot migration of a tab's presets out of QSettings into files."""
    key = LEGACY_KEYS.get(tab)
    if not key:
        return
    raw = settings.get(key, "")
    if not raw:
        return
    try:
        legacy = json.loads(raw)
    except Exception as exc:
        log.warning("preset_store: legacy %s unparseable (%s)", key, exc)
        return
    if not isinstance(legacy, dict) or not legacy:
        return
    log.info("preset_store: migrating %d preset(s) from %s to %s",
             len(legacy), key, tab_dir(tab))
    save_presets(tab, legacy)


def reveal_in_file_manager(path: Path) -> None:
    """Open `path` in the OS file manager. Creates the folder if missing."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.warning("preset_store: cannot create %s (%s)", path, exc)
        return
    p = str(path)
    if sys.platform == "darwin":
        os.system(f"open {shlex.quote(p)}")
    elif sys.platform == "win32":
        try:
            os.startfile(p)  # type: ignore[attr-defined]
        except OSError as exc:
            log.warning("preset_store: startfile %s failed (%s)", p, exc)
    else:
        os.system(f"xdg-open {shlex.quote(p)}")
