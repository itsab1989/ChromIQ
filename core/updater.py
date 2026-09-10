"""Background update checker — polls GitHub releases API, emits Qt signals."""
from __future__ import annotations

import json
import re
import ssl
import threading
import time
import urllib.request
from urllib.error import HTTPError, URLError

import certifi

from PyQt6.QtCore import QObject, pyqtSignal

from core.i18n import tr
from core.logger import get_logger
from core.version import APP_VERSION

log = get_logger(__name__)

_RELEASES_API = "https://api.github.com/repos/itsab1989/ChromIQ/releases?per_page=100"
#: The latest FULL release, however many pre-release tags sit above it.
_LATEST_API = "https://api.github.com/repos/itsab1989/ChromIQ/releases/latest"
_RELEASES_PAGE = "https://github.com/itsab1989/ChromIQ/releases"
#: THE WAY OUT WHEN THE API SAYS NO. GitHub's REST API allows **60 requests an
#: hour to a caller with no token, counted against the IP ADDRESS** and so
#: shared by everyone behind it: an office, a school, a household, anyone on
#: mobile carrier NAT. Past that it answers 403 (or 429) and ChromIQ used to
#: show the bare number, which tells a user nothing they can act on.
#: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
#: (read 2026-09-10)
#:
#: The releases feed is not that API. Measured from one address at one moment,
#: with the quota already exhausted: the API answered 403 with
#: ``x-ratelimit-remaining: 0`` while this feed answered 200 and listed every
#: tag. So a check that would have failed now succeeds.
_RELEASES_ATOM = "https://github.com/itsab1989/ChromIQ/releases.atom"
#: Settings key: the epoch second the quota frees again. While it is in the
#: future the API is not asked at all, because the answer is known.
_BLOCKED_UNTIL = "update_check_blocked_until"
#: The project's showcase page (Knut, 2026-08-12: linked from Preferences).
WEBSITE_URL = "https://itsab1989.github.io/ChromIQ/"

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


def _rate_limit_reset(headers) -> int | None:
    """The epoch second GitHub's quota frees, or ``None`` if this was not that.

    A 403 has more than one cause: a token-less caller past its hourly quota, a
    proxy refusing the request, a repository that has gone private. Only the
    first is worth a special message, and GitHub distinguishes it in the
    response itself, with ``x-ratelimit-remaining: 0``. Zero is returned when
    the quota is exhausted but the reset header is missing or unreadable, which
    means "rate limited, time unknown" and is still not ``None``.
    """
    if headers is None:
        return None
    try:
        remaining = headers.get("x-ratelimit-remaining")
        reset = headers.get("x-ratelimit-reset")
    except Exception:                      # a header object that is not one
        return None
    if remaining is None or str(remaining).strip() != "0":
        return None
    try:
        return max(0, int(str(reset).strip()))
    except (TypeError, ValueError):
        return 0


def _remember_rate_limit(reset: int) -> None:
    """Write down when the quota frees, so the next check skips the API.

    Asking again before then spends nothing and learns nothing: the answer is
    another 403. Failing to write it down is not worth an error, because the
    check still works through the feed.
    """
    try:
        from core.settings import AppSettings
        AppSettings().set(_BLOCKED_UNTIL, int(reset))
    except Exception:                      # a settings store we cannot reach
        log.debug("Could not record the update-check rate limit", exc_info=True)


def _api_is_blocked(now: float | None = None) -> bool:
    """Whether the quota is known to be spent, so the API should be skipped."""
    try:
        from core.settings import AppSettings
        until = float(AppSettings().get(_BLOCKED_UNTIL, 0) or 0)
    except Exception:
        return False
    return (time.time() if now is None else now) < until


def _tags_from_atom(xml: str) -> list[str]:
    """Every release tag named in the releases feed, newest first.

    The feed carries no draft entries, so nothing has to be filtered for that.
    It also carries no pre-release FLAG, which the API does give: here the tag
    NAME is the only signal, and this project spells every pre-release with a
    suffix (``v4.3.0-beta.2``), which :func:`_is_prerelease` already reads. A
    release marked pre-release on GitHub while carrying a final-looking tag
    would be misread by this path, and would be read correctly by the API path
    that runs whenever the quota allows.
    """
    return re.findall(r"releases/tag/([^\"'<\s]+)", xml)


class UpdateChecker(QObject):
    update_available = pyqtSignal(str)   # latest version tag, e.g. "v1.5.0"
    up_to_date       = pyqtSignal()
    check_failed     = pyqtSignal(str)   # error description
    #: Both routes are shut: the hourly quota is spent AND the feed could not
    #: be read. Carries the epoch second the quota frees, or 0 if GitHub did
    #: not say. A separate signal because the cure is not an error's cure:
    #: nothing is broken, and waiting fixes it.
    rate_limited     = pyqtSignal(int)

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

    @staticmethod
    def _open(url: str) -> bytes:
        req = urllib.request.Request(
            url, headers={"User-Agent": "ChromIQ-update-check"})
        ctx = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            return resp.read()

    @classmethod
    def _fetch(cls, url: str):
        return json.loads(cls._open(url))

    @classmethod
    def _fetch_tags_from_feed(cls) -> list[str]:
        """The tag names from the releases feed, which has no hourly quota."""
        return _tags_from_atom(cls._open(_RELEASES_ATOM).decode("utf-8", "replace"))

    def _candidates_from_api(self, running_is_pre: bool) -> list[str] | None:
        """Tag names from the REST API, or ``None`` if it has nothing to say."""
        if running_is_pre:
            # Pre-release users see pre-release tags as upgrade candidates;
            # stable users don't, so we never push someone from a final
            # release onto a beta.
            data = self._fetch(_RELEASES_API)
            if not isinstance(data, list):
                return None
            return [r["tag_name"] for r in data
                    if r.get("tag_name") and not r.get("draft", False)]
        # A stable build must NOT page through the releases list: in a busy
        # beta period the first page holds only beta tags, every one of them is
        # filtered out, and the check failed with "No release tag found" for
        # every stable user (#142). GitHub's /releases/latest returns the newest
        # full release directly, however many pre-releases sit above it.
        data = self._fetch(_LATEST_API)
        return ([data["tag_name"]]
                if isinstance(data, dict) and data.get("tag_name") else [])

    def _candidates_from_feed(self, running_is_pre: bool) -> list[str]:
        """The same question asked of the feed, which the quota does not cover.

        A stable build keeps its rule here too: only final tags are candidates,
        so nobody is walked from a release onto a beta by the fallback path.
        """
        tags = self._fetch_tags_from_feed()
        return tags if running_is_pre else [t for t in tags if not _is_prerelease(t)]

    def _run(self) -> None:
        running_is_pre = _is_prerelease(APP_VERSION)
        rate_limited_at: int | None = None
        candidates: list[str] | None = None

        # 1. The API, unless we already know this address has spent its hour.
        if not _api_is_blocked():
            try:
                candidates = self._candidates_from_api(running_is_pre)
                if candidates is None:
                    self._emit("check_failed",
                               tr("GitHub sent an answer ChromIQ could not read."))
                    return
            except HTTPError as exc:
                log.debug("Update check, API: %s", exc)
                rate_limited_at = _rate_limit_reset(getattr(exc, "headers", None))
                if rate_limited_at is None:
                    if exc.code == 404 and not running_is_pre:
                        # /releases/latest 404s when no full release exists.
                        self._emit("check_failed",
                                   tr("No finished release is published yet."))
                        return
                    self._emit("check_failed",
                               tr("GitHub answered {code}.").format(code=exc.code))
                    return
                _remember_rate_limit(rate_limited_at)
            except URLError as exc:
                log.debug("Update check, API: %s", exc)
                self._emit("check_failed", str(exc.reason))
                return
            except Exception as exc:
                log.debug("Update check, API: %s", exc)
                self._emit("check_failed", str(exc))
                return

        # 2. The feed, which the hourly quota does not cover. This is the whole
        #    point: being over the quota stops being a failure the user sees.
        if candidates is None:
            try:
                candidates = self._candidates_from_feed(running_is_pre)
            except Exception as exc:
                log.debug("Update check, feed: %s", exc)
                self._emit("rate_limited", int(rate_limited_at or 0))
                return

        if not candidates:
            self._emit("check_failed", tr("No release found to compare against."))
            return

        latest = max(candidates, key=_parse_version)
        if _parse_version(latest) > _parse_version(APP_VERSION):
            self._emit("update_available", latest)
        else:
            self._emit("up_to_date")
