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
import unicodedata
from glob import escape as glob_escape
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


def same_file_name(a: str, b: str) -> bool:
    """True when presets named `a` and `b` would be stored in the same files.

    "a/b" and "a_b" are two names and one ``.json`` (and one ``.ti1``), and on
    a case-insensitive disk so are "Mine" and "mine". Saving the second one
    replaced the first one's files while both names stayed in the list.
    """
    def key(n: str) -> str:
        return unicodedata.normalize("NFC", _sanitize(n)).casefold()
    return key(a) == key(b)


def _recorded_names(d: Path) -> dict[str, Path]:
    """``{listed name: .json}`` for every preset file in `d`, as
    :func:`load_presets` lists them."""
    out: dict[str, Path] = {}
    claimed: dict[str, Path] = {}
    docs = []
    for p in sorted(d.glob("*.json")):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            log.warning("preset_store: skipping malformed %s (%s)", p, exc)
            continue
        if isinstance(doc, dict):
            docs.append((p, doc))
    # The file that is still called what it records goes first, so it keeps
    # the name when a copy of it claims the same one.
    docs.sort(key=lambda pd: not _is_its_own_file(pd[1], pd[0]))
    for p, doc in docs:
        name = str(doc.get("name") or "") or p.stem
        if name in claimed:
            name = unicodedata.normalize("NFC", p.stem)
        claimed[name] = p
        out[name] = p
    return out


def _is_its_own_file(doc: dict, p: Path) -> bool:
    name = str(doc.get("name") or "")
    nfc = unicodedata.normalize
    return bool(name) and nfc("NFC", _sanitize(name)) == nfc("NFC", p.stem)


def find_sidecar(tab: str, name: str, suffix: str) -> Path:
    """The bundled file of preset `name`, tolerating a rename by hand.

    :func:`sidecar_path` when that file exists. Otherwise the one beside the
    ``.json`` that records this name: a preset file renamed by hand, or by a
    download (an attachment on the issue tracker loses its spaces), keeps its
    name inside and its ``.ti1`` under the new file name, and the preset then
    quietly built from targen instead of its own patch set. Always returns a
    path; the caller checks ``is_file()``.
    """
    primary = sidecar_path(tab, name, suffix)
    if primary.is_file():
        return primary
    own = _recorded_names(tab_dir(tab)).get(name)
    if own is not None:
        other = own.with_suffix(suffix)
        if other.is_file():
            return other
    return primary


def load_presets(tab: str, settings: Any = None) -> dict[str, Any]:
    """Return ``{name: payload_dict}`` for `tab`.

    On first call for a tab (when the subfolder doesn't yet exist) the
    legacy QSettings preset dict, if any, is migrated to disk before the
    folder is scanned.

    A preset is listed under the name recorded inside its file. TWO FILES
    CLAIMING ONE NAME ARE TWO PRESETS: a copy made in the file manager ("Mine
    copy.json" still says "Mine") showed as one, and the next save deleted the
    other file. The copy is listed under its own file name instead.
    """
    d = tab_dir(tab)
    if not d.exists():
        d.mkdir(parents=True, exist_ok=True)
        if settings is not None:
            _migrate_from_settings(tab, settings)
    out: dict[str, Any] = {}
    for name, p in _recorded_names(d).items():
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — logged by _recorded_names
            continue
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

    A preset whose ``.json`` was not called what it records is written under
    the name's own file, and its bundled files (the ``.ti1``) move with it:
    otherwise the first save orphaned them under the old file name.
    """
    d = tab_dir(tab)
    d.mkdir(parents=True, exist_ok=True)
    before = _recorded_names(d)
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
            continue
        old = before.get(name)
        if old is not None and old.name != fname:
            for extra in d.glob(glob_escape(old.stem) + ".*"):
                if extra.suffix.lower() == ".json" or extra.stem != old.stem:
                    continue
                target = d / (_sanitize(name) + extra.suffix)
                if not target.exists():
                    try:
                        extra.rename(target)
                    except OSError as exc:
                        log.warning("preset_store: could not move %s (%s)",
                                    extra, exc)
    # THE FILE JUST WRITTEN IS NOT A LEFTOVER, WHATEVER IT IS CALLED. On a
    # case- and normalisation-insensitive disk (APFS, NTFS) writing
    # "Mine.json" goes into an existing "mine.json", or into a "Grün.json"
    # spelled in decomposed form, and the directory keeps that spelling; the
    # name test below then deleted the preset it had just saved. Saving ANY
    # preset lost it.
    written: set[tuple[int, int]] = set()
    for fname in wanted:
        try:
            st = (d / fname).stat()
        except OSError:
            continue
        written.add((st.st_dev, st.st_ino))
    for p in d.glob("*.json"):
        if p.name not in wanted:
            try:
                st = p.stat()
                if (st.st_dev, st.st_ino) in written:
                    continue
            except OSError:
                pass
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
