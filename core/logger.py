"""Centralised logging setup for ChromIQ."""
from __future__ import annotations

import logging
import logging.handlers
import sys
from datetime import datetime

from core.platform_paths import log_dir


def _log_path():
    base = log_dir()
    base.mkdir(parents=True, exist_ok=True)
    return base / "chromiq.log"


def _write_session_banner(path) -> None:
    try:
        from core.version import APP_VERSION
    except Exception:
        APP_VERSION = "unknown"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    py = sys.version.split()[0]
    banner = (
        "\n"
        "================================================================================\n"
        f"=== ChromIQ session started — {ts}  v{APP_VERSION}  ({sys.platform}, py {py})\n"
        "================================================================================\n"
    )
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(banner)
    except Exception:
        pass


def configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        # STILL QUIET THEM. Pillow imports (and logs) long before this is first
        # called in some entry points, so a handler can already be installed —
        # and the early return then skipped the one line that keeps a user's
        # log readable.
        _quiet_third_party()
        return
    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    path = _log_path()
    _write_session_banner(path)

    fh = logging.handlers.RotatingFileHandler(
        path, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    _quiet_third_party()


#: Libraries that log at DEBUG on the root logger and drown ChromIQ's own
#: diagnostics. Measured on a log Knut sent for a nine-minute session
#: (2026-08-27): 2,315 lines, of which 1,813 were Pillow's per-tag TIFF/PNG
#: chatter and only 101 were ChromIQ saying anything about what it did. With a
#: 5 MB rotation that noise can evict the very traceback the log was sent for,
#: so these are held at WARNING — where a real problem still comes through.
_NOISY_LIBRARIES = ("PIL", "matplotlib", "urllib3", "fontTools")


def _quiet_third_party() -> None:
    for name in _NOISY_LIBRARIES:
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
