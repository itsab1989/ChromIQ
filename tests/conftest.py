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

import pytest

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
# Demo projects: built ONCE for the whole session, shared by every test file.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def demo_projects_root(tmp_path_factory):
    """Every demo project, built once per session.

    Each builder shells out to real ArgyllCMS (targen, colprof) and costs
    30-70 seconds. They were being built per test, then per file — two separate
    session fixtures in two files, so the same project was built twice in one
    gate run. One fixture here means one build for the whole suite.

    Tests must COPY what they use: ``Project.load`` migrates in place, so a
    shared tree would let one test's migration change what the next one sees.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from make_demo_projects import (build_full, build_legacy_v1,
                                    build_legacy_v2, build_verify_history)
    root = tmp_path_factory.mktemp("demo-projects")
    for build in (build_full, build_verify_history,
                  build_legacy_v1, build_legacy_v2):
        build(root)
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
