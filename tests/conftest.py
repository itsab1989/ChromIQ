"""Shared pytest fixtures.

Neutralise the layout editor's real render path for the whole suite.
``Ti2RelayoutDialog._regenerate`` builds and starts a ``_RegenWorker`` — a
background ``printtarg`` run. On a machine without ArgyllCMS (e.g. a Windows
dev box or CI), that render *fails*, and the worker's ``done`` signal carries an
exception. Because the signal is queued, it is delivered during a *later*
test's event processing (pytest-qt drains the event queue in
``pytest_runtest_setup``), where ``_on_regen_done`` pops a modal
``QMessageBox.warning`` — which blocks the headless suite forever. On macOS with
Argyll installed the render succeeds, so the modal never appears and the leak is
invisible there; this is purely a "passes on Mac, hangs on Windows" hazard.

No test exercises the dialog's real worker (the regenerate logic is covered
directly via ``workflow.ti2_relayout``), and tests that need bespoke behaviour
still override ``_regenerate`` on their own instance. So default it to a no-op
at the class level: no real subprocess, no cross-test signal leak, no modal.
"""
from pathlib import Path

import os
import shutil
import sys
import tempfile

import pytest

# Make helper modules that live beside the tests (e.g. ``tests/_fontcheck.py``)
# importable with a bare ``import _fontcheck`` from any test. pytest puts the
# rootdir on sys.path but not reliably this directory, so without it such an
# import fails depending on the import mode.
sys.path.insert(0, str(Path(__file__).resolve().parent))

# On Windows/ARM, make freetype-py find our vendored ARM64 FreeType before any
# test imports `freetype` (e.g. test_vector_pdf collects it at module load), so
# the vector-PDF tests actually run there instead of skipping (#72). No-op on
# every other platform.
from core.freetype_bootstrap import ensure_freetype_library

ensure_freetype_library()


@pytest.fixture(autouse=True)
def _no_real_editor_render(monkeypatch):
    try:
        from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog
    except Exception:
        # PyQt6 unavailable (or import error) — nothing to stub.
        return
    monkeypatch.setattr(Ti2RelayoutDialog, "_regenerate",
                        lambda self, *a, **k: None, raising=False)


# ---------------------------------------------------------------------------
# The suite never writes into the user's real ChromIQ folder.
#
# Basti, 2026-08-01: *"some of those tests create files on my machine every time
# they run … until now i deleted them manually"* — 77 project folders named
# `Printer_Paper_Type_Instr_<timestamp>` had accumulated, one per gate run.
#
# The trap is quiet. Overriding a test's QSettings is not enough: with
# `custom_output_path` left at its default of "", the FileManager falls back to
# ~/ChromIQ, and anything that asks where it is working makes
# `get_target_name()` INVENT that name and create the folder. A test can look
# perfectly isolated and still do this.
#
# So it is caught here rather than left to review, and named per test. Nothing
# is ever deleted: the folder holds real projects, and a test suite that tidies
# a developer's data is a worse idea than one that leaves a mess.
# ---------------------------------------------------------------------------
_REAL_CHROMIQ = Path.home() / "ChromIQ"


def _real_chromiq_entries() -> set:
    try:
        return {p.name for p in _REAL_CHROMIQ.iterdir()}
    except OSError:
        return set()


@pytest.fixture(autouse=True)
def _never_touch_the_real_chromiq_folder():
    before = _real_chromiq_entries()
    yield
    new = sorted(_real_chromiq_entries() - before)
    assert not new, (
        "this test wrote into the real ~/ChromIQ folder: "
        f"{new}\n"
        "Point the settings at tmp_path — overriding QSettings alone leaves "
        "custom_output_path at its default, which IS ~/ChromIQ:\n"
        '    s.set("custom_output_path", str(tmp_path / "out"))\n'
        "Nothing has been deleted; remove the stray folder(s) by hand if you "
        "want them gone."
    )


# ---------------------------------------------------------------------------
# Two-tier suite (#123 follow-up): heavy end-to-end profile builds carry
# @pytest.mark.slow and are skipped in everyday runs — `pytest --runslow`
# includes them, and the release gate always runs with --runslow.
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true", default=False,
                     help="also run the slow end-to-end build tests")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        return
    skip = pytest.mark.skip(reason="slow end-to-end build — use --runslow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)

# ---------------------------------------------------------------------------
# Demo projects: built once, then CACHED ON DISK across workers and runs.
# ---------------------------------------------------------------------------
def _demo_cache_key() -> str:
    """What the built projects actually depend on.

    Two things decide whether a cached tree is still the right answer: the
    generator that produced it, and the ArgyllCMS that did the work. Anything
    else changing (a test, the app) does not alter these files, so the cache
    survives it — which is the whole point.
    """
    import hashlib

    h = hashlib.sha256()
    h.update(_DEMO_GENERATOR.read_bytes())
    # The Argyll binaries: identity by size + mtime, so an upgrade invalidates
    # the cache rather than silently testing yesterday's output.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    try:
        from make_demo_projects import _argyll
        for tool in ("targen", "colprof", "printtarg", "fakeread"):
            try:
                st = Path(_argyll(tool)).stat()
                h.update(f"{tool}:{st.st_size}:{int(st.st_mtime)}".encode())
            except Exception:            # noqa: BLE001 — a missing tool is
                h.update(f"{tool}:missing".encode())   # itself part of the key
    except Exception:                    # noqa: BLE001
        h.update(b"argyll-unresolvable")
    return h.hexdigest()[:16]


#: Where the cache lives. Beside the repo rather than in it, so it is never
#: committed and never confuses a `git status` before a release.
_DEMO_GENERATOR = Path(__file__).resolve().parents[1] / "scripts" / "make_demo_projects.py"
_DEMO_CACHE_HOME = Path(
    os.environ.get("CHROMIQ_DEMO_CACHE",
                   Path(tempfile.gettempdir()) / "chromiq-demo-projects-cache"))


def _build_demo_projects(into: Path) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from make_demo_projects import (build_full, build_legacy_v1,
                                    build_legacy_v2, build_verify_history)
    for build in (build_full, build_verify_history,
                  build_legacy_v1, build_legacy_v2):
        build(into)


@pytest.fixture(scope="session")
def demo_projects_root(tmp_path_factory):
    """Every demo project, built once and then reused.

    Each builder shells out to real ArgyllCMS (targen, colprof) and costs
    30-70 seconds; the four together are around **four minutes**, and that
    setup is the single longest thing in the whole suite.

    "Session-scoped" is not enough on its own. Under ``pytest-xdist`` a session
    is **per worker process**, so every worker that touches this fixture built
    its own copy: with ``--dist loadfile`` and two files needing it, the gate
    paid for the same four minutes twice, in parallel, and could never finish
    faster than one of them. Measured on the beta.141 tree:

        234.26s setup  tests/test_report_readable_on_dark.py
        229.38s setup  tests/test_legacy_migration.py
         89.99s call   <the next slowest thing in the entire suite>

    So the tree is cached on disk instead, keyed by the generator and the
    ArgyllCMS that built it (see :func:`_demo_cache_key`). The first run after
    either changes pays the four minutes; every run after that starts with the
    projects already there. Delete the folder, or point ``CHROMIQ_DEMO_CACHE``
    somewhere else, to force a rebuild.

    Tests must still COPY what they use: ``Project.load`` migrates in place, so
    a shared tree would let one test's migration change what the next one sees.
    That is also why the cache is only ever READ from — every consumer copies.
    """
    cached = _DEMO_CACHE_HOME / _demo_cache_key()
    ready = cached / ".complete"
    if ready.is_file():
        return cached

    # Build into a private folder and move it into place atomically, so a
    # half-built tree can never be picked up — by another worker racing us, or
    # by a later run after this one was interrupted.
    cached.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="demo-build-", dir=str(cached.parent)))
    try:
        _build_demo_projects(staging)
        (staging / ".complete").write_text(_demo_cache_key())
        try:
            os.replace(staging, cached)
        except OSError:
            # Another worker got there first — theirs is as good as ours.
            shutil.rmtree(staging, ignore_errors=True)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    if ready.is_file():
        return cached
    # Cache unusable for some reason: fall back to a throwaway build rather
    # than failing the suite over an optimisation.
    root = tmp_path_factory.mktemp("demo-projects")
    _build_demo_projects(root)
    return root


@pytest.fixture
def demo_project(demo_projects_root, tmp_path):
    """Give this test its own copy of a demo project, by name."""
    import shutil

    def _copy(name: str) -> Path:
        dst = tmp_path / name
        if not dst.exists():
            shutil.copytree(demo_projects_root / name, dst)
        return dst

    return _copy


# ---- #137 calibration run type -------------------------------------------
# Imported so every calibration test file gets them without repeating the
# temp-folder isolation, which is the one thing they must not get wrong.
from tests.conftest_calibration import (      # noqa: E402,F401
    CalSettings, cal_home, cal_settings, cal_project)
