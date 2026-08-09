"""Auto-detect the ArgyllCMS binary directory."""
from __future__ import annotations

from pathlib import Path
from shutil import which

from core.logger import get_logger
from core.platform_paths import argyll_candidate_dirs
from core.resource_path import argyll_binary

log = get_logger(__name__)

_REQUIRED = ("targen", "printtarg", "chartread", "colprof")
_OPTIONAL = ("profcheck", "printcal", "applycal", "iccgamut", "viewgam")


def all_tools_present(bin_dir: Path) -> bool:
    return all((bin_dir / argyll_binary(t)).exists() for t in _REQUIRED)


def resolve_ref_dir(bin_dir: Path | str) -> Path | None:
    """Locate ArgyllCMS's ``ref/`` folder (ClayRGB1998.icm, standard target
    ``.cht`` files, …) for a given ``bin`` directory.

    ``ref/`` sits beside ``bin`` in a real Argyll install. Homebrew, though,
    exposes only symlinks in ``/opt/homebrew/bin`` that point into the Cellar
    (``…/argyll-cms/<ver>/bin``), where the real ``ref/`` lives — so a plain
    ``bin/../ref`` misses it (Knut). We therefore try, in order: ``bin/../ref``
    directly, then the ``../ref`` of the *resolved* location of each Argyll
    binary in ``bin`` (following the Homebrew symlinks). Returns the first
    existing ``ref/``, or None.
    """
    bin_dir = Path(bin_dir)
    if not str(bin_dir):
        return None
    direct = bin_dir.parent / "ref"
    if direct.is_dir():
        return direct
    for tool in _REQUIRED:
        exe = bin_dir / argyll_binary(tool)
        if exe.exists():
            real_ref = exe.resolve().parent.parent / "ref"
            if real_ref.is_dir():
                return real_ref
    return None


def find_ref_profile(bin_dir: "Path | str", names: "tuple[str, ...]") -> str:
    """The first profile among *names* that exists, as an absolute path string.

    Searched in ArgyllCMS's ``ref/`` folder (through :func:`resolve_ref_dir`,
    so Homebrew's symlinked layout resolves too), then among ChromIQ's bundled
    copies in ``assets/profiles/``. Empty string when none is found.

    Lifted out of ``TabProfile._default_gamut_src`` so the profile-build tab
    and the verification print conversion answer "which source profile?" the
    same way instead of each keeping its own search.
    """
    from core.resource_path import resource_path
    ref_dir = resolve_ref_dir(Path(bin_dir)) if str(bin_dir) else None
    if ref_dir is not None:
        for name in names:
            candidate = ref_dir / name
            if candidate.exists():
                return str(candidate)
    for name in names:
        bundled = resource_path(f"assets/profiles/{name}")
        if Path(bundled).exists():
            return str(bundled)
    return ""


def find_argyll_bin_path() -> Path | None:
    """Return the first directory that contains all required ArgyllCMS tools, or None."""

    # 1. Check the system PATH first. Resolve symlinks: Homebrew's
    # /opt/homebrew/bin holds only links into the Cellar — the REAL install
    # dir (…/argyll-cms/<ver>/bin) is what ChromIQ needs, because ``ref/``
    # (ClayRGB1998.icm, standard target .cht files) is a sibling of THAT bin,
    # not of /opt/homebrew/bin (Knut, #108). Prefer whichever candidate dir
    # actually has a resolvable ref/; only fall back to a ref-less dir if none
    # does.
    fallback: Path | None = None
    for tool in _REQUIRED:
        found = which(argyll_binary(tool))
        if not found:
            continue
        real = Path(found).resolve()
        for candidate in (real.parent, Path(found).parent):
            if all_tools_present(candidate):
                if resolve_ref_dir(candidate) is not None:
                    log.info("ArgyllCMS found in PATH at %s (ref/ resolved)", candidate)
                    return candidate
                if fallback is None:
                    fallback = candidate
    if fallback is not None:
        log.info("ArgyllCMS found in PATH at %s (no ref/ nearby)", fallback)
        return fallback

    # 2. Fall back to platform-specific well-known locations
    for candidate in argyll_candidate_dirs():
        if all_tools_present(candidate):
            log.info("ArgyllCMS auto-detected at %s", candidate)
            return candidate

    log.warning("ArgyllCMS binaries not found in any known location")
    return None
