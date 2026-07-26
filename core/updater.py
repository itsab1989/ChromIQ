"""Background update checker — polls GitHub releases API, emits Qt signals."""
from __future__ import annotations

import json
import re
import ssl
import threading
import urllib.request
from urllib.error import URLError

import certifi

from PyQt6.QtCore import QObject, pyqtSignal

from core.logger import get_logger
from core.version import APP_VERSION

log = get_logger(__name__)

_RELEASES_API = "https://api.github.com/repos/itsab1989/ChromIQ/releases?per_page=30"
_RELEASES_PAGE = "https://github.com/itsab1989/ChromIQ/releases"

_VERSION_RE = re.compile(
    r"^v?(\d+(?:\.\d+)*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)


def _parse_version(tag: str) -> tuple:
    """Parse a SemVer-ish tag into a tuple that sorts by precedence.

    A final release sorts above any pre-release with the same base
    (3.5.0 > 3.5.0-beta.3). Pre-release identifiers are compared
    dot-by-dot with numeric identifiers sorting below alphanumerics,
    matching SemVer 2.0.0. Unparseable tags sort below everything so
    they can never claim to be newer than a real version.
    """
    m = _VERSION_RE.match(tag.strip())
    if not m:
        return ((-1,),)
    base, pre = m.groups()
    base_nums = tuple(int(x) for x in base.split("."))
    if pre is None:
        return (base_nums, 1)
    pre_parts = tuple(
        (0, int(p)) if p.isdigit() else (1, p) for p in pre.split(".")
    )
    return (base_nums, 0, pre_parts)


def _is_prerelease(tag: str) -> bool:
    m = _VERSION_RE.match(tag.strip())
    return bool(m and m.group(2))


class UpdateChecker(QObject):
    update_available = pyqtSignal(str)   # latest version tag, e.g. "v1.5.0"
    up_to_date       = pyqtSignal()
    check_failed     = pyqtSignal(str)   # error description

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    def check_async(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _emit(self, name: str, *args) -> None:
        """Emit signal *name*, unless this checker no longer exists.

        _run() is executed on a worker thread. If the window closed while the
        check was in flight, the C++ object behind this QObject is already gone
        and touching one of its signals raises RuntimeError — which then escaped
        as an unhandled thread exception, because the error handler tried to
        emit as well. There is nobody left to tell, so dropping it is right.
        """
        try:
            getattr(self, name).emit(*args)
        except RuntimeError:          # the checker was destroyed meanwhile
            pass

    def _run(self) -> None:
        try:
            req = urllib.request.Request(
                _RELEASES_API,
                headers={"User-Agent": "ChromIQ-update-check"},
            )
            ctx = ssl.create_default_context(cafile=certifi.where())
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                data = json.loads(resp.read())
            if not isinstance(data, list):
                self._emit("check_failed", "Unexpected response from releases API.")
                return

            # Pre-release users see pre-release tags as upgrade candidates;
            # stable users don't, so we never push someone from a final
            # release onto a beta.
            running_is_pre = _is_prerelease(APP_VERSION)
            candidates = [
                r["tag_name"]
                for r in data
                if r.get("tag_name")
                and not r.get("draft", False)
                and (running_is_pre or not r.get("prerelease", False))
            ]
            if not candidates:
                self._emit("check_failed", "No release tag found.")
                return

            latest = max(candidates, key=_parse_version)
            if _parse_version(latest) > _parse_version(APP_VERSION):
                self._emit("update_available", latest)
            else:
                self._emit("up_to_date")
        except URLError as exc:
            log.debug("Update check failed: %s", exc)
            self._emit("check_failed", str(exc.reason))
        except Exception as exc:
            log.debug("Update check failed: %s", exc)
            self._emit("check_failed", str(exc))
