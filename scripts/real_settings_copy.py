"""A throw-away COPY of the user's real ChromIQ preferences, for seeding sandboxes.

The real store (~/Library/Preferences/com.chromiq.ChromIQ.plist, Qt domain
QSettings("ChromIQ", "ChromIQ")) must stay untouched by anything under
scripts/ and tests/. Opening it with QSettings is not read-only in practice:
QSettings can write back on sync or on destruction, and cfprefsd caches it.
So a driver that wants to start from the user's values reads this COPY, never
the real file. Nothing here writes to the real plist or domain.
"""
from __future__ import annotations

import atexit
import plistlib
import shutil
import subprocess
import tempfile
from pathlib import Path

DOMAIN = "com.chromiq.ChromIQ"
_REAL = Path.home() / "Library" / "Preferences" / (DOMAIN + ".plist")


def copy_of_real_preferences(dst_dir: Path | None = None) -> Path:
    """Return the path of a .plist COPY of the real preferences.

    `defaults export` reads through cfprefsd and writes only the destination;
    failing that the plist file is copied; with no preferences at all an empty
    plist is written, so the caller gets an empty store.
    """
    if dst_dir is None:
        dst_dir = Path(tempfile.mkdtemp(prefix="chromiq-plist-copy-"))
        atexit.register(shutil.rmtree, str(dst_dir), True)
    else:
        dst_dir = Path(dst_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / (DOMAIN + ".plist")
    try:
        r = subprocess.run(["defaults", "export", DOMAIN, str(dst)],
                           capture_output=True, timeout=30)
        if r.returncode == 0 and dst.is_file() and dst.stat().st_size > 0:
            return dst
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        if _REAL.is_file():
            shutil.copy2(_REAL, dst)
            return dst
    except OSError:
        pass
    with open(dst, "wb") as fh:
        plistlib.dump({}, fh)
    return dst
