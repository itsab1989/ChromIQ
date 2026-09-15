"""B8-221 — "Nothing was changed in your project", said after the archive.

`_on_build` -> `_confirm_rebuild_over_verifications` -> `_archive_superseded_profile`
MOVES the run's built profile into `runs/runN/old/<date>/` and EVERY dated
verification measurement into `verifications/old/<date>/`, and only then is
colprof launched. With the ArgyllCMS folder pointing somewhere wrong, colprof
never starts, `_on_build_done(-1)` runs, and `_report_if_the_tool_could_not_start`
shows a window that ends with the words **"Nothing was changed in your project."**

DRIVEN ON SCREEN (combined round 8, `D-result.json`,
`D2-ChromIQ-could-not-start-colprof.png`) on a real project holding a real
profile and two real dated verification measurements. After *Build here anyway*:

* `runs/run1/old/2026-09-16_003327/Demo-Switching.icc` — the run held **no
  profile at all**,
* `verifications/old/2026-09-16_003327/` holding both dated folders,
* and that window, on screen, saying nothing had been changed.

Round 7 recorded this as a LEAD it could not force, and said why: its two probes
pointed `argyll_bin_path` at nothing and `ArgyllRunner._resolve` fell back to a
bare `PATH` lookup, which found a perfectly good colprof. Removing `PATH` as
well is what a real machine looks like, because ChromIQ's default is
`/Applications/Argyll/bin` and nothing puts ArgyllCMS on `PATH`.

The fix asks BEFORE anything is moved, which is round 7's own fix for the
archive's log lines in the same method: move the step above the question rather
than undo it below. Nothing is moved, so the sentence the window already says is
true, and no new message text was needed.
"""
from __future__ import annotations

import ast
import inspect
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_profile import TabProfile      # noqa: E402


# ---- the order, which is the fix ---------------------------------------
def _on_build_without_prose() -> str:
    """`_on_build` with its docstring and every `#` comment STRIPPED.

    Round 7 learned this the hard way and wrote it down: an order test that
    indexes raw source goes red on a correct tree the moment a comment happens
    to name the thing being looked for.
    """
    import textwrap
    src = textwrap.dedent(inspect.getsource(TabProfile._on_build))
    tree = ast.parse(src)
    fn = tree.body[0]
    if (fn.body and isinstance(fn.body[0], ast.Expr)
            and isinstance(fn.body[0].value, ast.Constant)):
        fn.body = fn.body[1:]
    return ast.unparse(fn)


def test_the_refusal_is_asked_from_on_build():
    assert "_refuse_when_the_profiler_is_not_installed" in _on_build_without_prose()


def test_the_refusal_comes_before_the_question_that_archives():
    body = _on_build_without_prose()
    assert (body.index("_refuse_when_the_profiler_is_not_installed")
            < body.index("_confirm_rebuild_over_verifications")), (
        "the build is refused AFTER the question that moves the profile and "
        "every dated verification measurement out of the way, so they are "
        "archived for a build that never happens and the window still says "
        "nothing was changed")


def test_the_refusal_stops_the_build():
    body = _on_build_without_prose()
    i = body.index("_refuse_when_the_profiler_is_not_installed")
    assert "return" in body[i:i + 140]


def test_the_window_still_claims_nothing_was_changed():
    """The guard above is the only thing making this sentence true. If the
    sentence ever goes, this test should be read again rather than deleted."""
    src = inspect.getsource(TabProfile._report_if_the_tool_could_not_start)
    assert "Nothing was changed in your project." in src


# ---- can the tool be launched at all -----------------------------------
def test_a_path_install_is_not_called_missing(qapp, tmp_path, monkeypatch):
    """`_resolve` answers with a bare NAME when the configured folder holds
    nothing, precisely so a PATH install still works. A bare `Path.is_file()`
    on that answer would call a perfectly good ArgyllCMS missing and refuse a
    build that would have run."""
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

    fake_bin = tmp_path / "on-the-path"
    fake_bin.mkdir()
    (fake_bin / "colprof").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (fake_bin / "colprof").chmod(0o755)
    s = AppSettings()
    s.set("argyll_bin_path", str(tmp_path / "a-folder-with-no-argyll"))
    monkeypatch.setenv("PATH", str(fake_bin))
    assert ArgyllRunner(s).tool_is_installed("colprof") is True


def test_a_missing_tool_is_reported_missing(qapp, tmp_path, monkeypatch):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

    s = AppSettings()
    s.set("argyll_bin_path", str(tmp_path / "a-folder-with-no-argyll"))
    monkeypatch.setenv("PATH", "")
    assert ArgyllRunner(s).tool_is_installed("colprof") is False


def test_a_folder_holding_something_unrunnable_is_not_installed(qapp, tmp_path,
                                                                monkeypatch):
    """A file called colprof that cannot be executed starts no better than one
    that is not there — and that is how a half-copied install looks."""
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "colprof").write_text("not a program", encoding="utf-8")
    (bin_dir / "colprof").chmod(0o644)
    s = AppSettings()
    s.set("argyll_bin_path", str(bin_dir))
    monkeypatch.setenv("PATH", "")
    assert ArgyllRunner(s).tool_is_installed("colprof") is False


# ---- the behaviour, on a real run --------------------------------------
@pytest.fixture
def run_with_a_profile_and_a_verification(tmp_path):
    """A run holding a built profile and one dated verification measurement —
    the only state in which the archive question is asked at all."""
    from core.file_manager import Project

    root = tmp_path / "projects" / "B8221"
    rundir = root / "runs" / "run1"
    (rundir / "verifications" / "2026-05-20_090500").mkdir(parents=True)
    (root / "project.json").write_text(json.dumps(
        {"schema_version": 2, "name": "B8221", "current_run": "run1",
         "runs": ["run1"]}), encoding="utf-8")
    for ext in (".ti1", ".ti2", ".ti3", ".icc"):
        (rundir / f"B8221{ext}").write_text("x", encoding="utf-8")
    (rundir / "verifications" / "2026-05-20_090500"
     / "B8221-verify.ti3").write_text("x", encoding="utf-8")
    proj = Project.load(root)
    return proj, proj.run("run1"), rundir


def test_the_question_that_archives_is_never_asked_when_the_builder_is_missing(
        qapp, tmp_path, monkeypatch, run_with_a_profile_and_a_verification):
    proj, run, rundir = run_with_a_profile_and_a_verification
    from core.settings import AppSettings
    from ui.main_window import MainWindow

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("session_project", "")
    s.set("restore_last_session", False)
    s.set("profile_engine_beta", False)
    s.set("argyll_bin_path", str(tmp_path / "a-folder-with-no-argyll"))
    monkeypatch.setenv("PATH", "")

    w = MainWindow(s)
    try:
        # AFTER the window is built. `MainWindow._check_argyll_binaries(initial=
        # True)` AUTO-DETECTS a working installation and WRITES the path back,
        # so a bad path set before construction is silently corrected and the
        # test measures a machine that has ArgyllCMS. The same trap caught this
        # round's first on-screen drive.
        s.set("argyll_bin_path", str(tmp_path / "a-folder-with-no-argyll"))
        assert not w._runner.tool_is_installed("colprof"), (
            "colprof is findable, so this would measure a build that runs")
        tab = w._tab_profile
        asked: list[str] = []
        monkeypatch.setattr(
            type(tab), "_confirm_rebuild_over_verifications",
            lambda self: (asked.append("asked"), True)[1])
        shown: list[str] = []
        monkeypatch.setattr(
            type(tab), "_report_if_the_tool_could_not_start",
            lambda self: (shown.append(self._runner.last_failed_to_start),
                          True)[1])
        tab._ti3_path = rundir / "B8221.ti3"
        tab._on_build()
        qapp.processEvents()

        assert shown == ["colprof"], (
            f"the build was not refused for a missing colprof: {shown!r}")
        assert asked == [], (
            "the question that MOVES the profile and every dated verification "
            "measurement was asked for a build that cannot start")
    finally:
        w.close()


def test_a_build_that_cannot_start_leaves_the_profile_where_it_was(
        qapp, tmp_path, monkeypatch, run_with_a_profile_and_a_verification):
    """The user-facing half: after the refusal the run still HOLDS its profile
    and its verification, so "Nothing was changed in your project" is true."""
    proj, run, rundir = run_with_a_profile_and_a_verification
    from core.settings import AppSettings
    from ui.main_window import MainWindow

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("session_project", "")
    s.set("restore_last_session", False)
    s.set("profile_engine_beta", False)
    s.set("argyll_bin_path", str(tmp_path / "a-folder-with-no-argyll"))
    monkeypatch.setenv("PATH", "")

    w = MainWindow(s)
    try:
        s.set("argyll_bin_path", str(tmp_path / "a-folder-with-no-argyll"))
        assert not w._runner.tool_is_installed("colprof")
        tab = w._tab_profile
        monkeypatch.setattr(type(tab), "_report_if_the_tool_could_not_start",
                            lambda self: True)
        tab._ti3_path = rundir / "B8221.ti3"
        tab._on_build()
        qapp.processEvents()

        assert (rundir / "B8221.icc").is_file(), (
            "the run's profile was moved out of the way for a build that "
            "never started")
        assert not (rundir / "old").exists(), (
            f"an archive was made anyway: {sorted((rundir / 'old').iterdir())}")
        assert (rundir / "verifications" / "2026-05-20_090500"
                / "B8221-verify.ti3").is_file()
        assert not (rundir / "verifications" / "old").exists()
    finally:
        w.close()


def test_the_refusal_stands_down_for_the_profile_engine(qapp, tmp_path,
                                                        monkeypatch):
    """With the engine on, the build may not need ArgyllCMS at all. Refusing
    there would take a working feature away over a tool it does not run."""
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

    s = AppSettings()
    s.set("profile_engine_beta", True)
    s.set("argyll_bin_path", str(tmp_path / "nowhere"))
    monkeypatch.setenv("PATH", "")

    class _Tab:
        _settings = s
        _runner = ArgyllRunner(s)
        _refuse = TabProfile._refuse_when_the_profiler_is_not_installed

    class _P:
        ti3_path = tmp_path / "nothing.ti3"

    assert _Tab._refuse(_Tab(), _P()) is False


# ---- round 7's second lead, settled ------------------------------------
def test_the_project_manifest_is_written_atomically(tmp_path):
    """`project.json` was the one manifest still written with a plain
    `write_text`, and it is the one that decides whether a project opens at
    all: it names `current_run` and every run. `Run.load_meta` survives an
    unreadable `meta.json` by treating it as absent; nothing does that for the
    manifest.

    Knut, #130 (2026-08-06): *"Write the updated JSON data to a temporary file
    in the same directory, then rename (replace) the original file with the
    temporary one. This prevents file corruption if the process crashes
    mid-write."*

    Recorded as a lead by combined round 7 and closed here. GRADED HONESTLY: a
    consistency fix against a rule already written down, not a fault anybody
    has been shown.
    """
    import core.file_manager as fm

    import textwrap

    tree = ast.parse(textwrap.dedent(
        inspect.getsource(fm.Project.save_manifest)))
    fn = tree.body[0]
    if (fn.body and isinstance(fn.body[0], ast.Expr)
            and isinstance(fn.body[0].value, ast.Constant)):
        fn.body = fn.body[1:]       # the docstring NAMES write_text, in prose
    body = ast.unparse(fn)
    assert "write_json_atomically" in body, (
        "the project manifest is written without the atomic write every other "
        "manifest in the project uses")
    assert "write_text" not in body


def test_the_manifest_really_survives_a_write_that_fails(tmp_path, monkeypatch):
    """Proof the mechanism works and not just that the name appears: a write
    that dies partway leaves the PREVIOUS manifest readable."""
    import core.file_manager as fm
    from core.file_manager import Project

    root = tmp_path / "P"
    (root / "runs" / "run1").mkdir(parents=True)
    (root / "project.json").write_text(json.dumps(
        {"schema_version": 2, "name": "P", "current_run": "run1",
         "runs": ["run1"]}), encoding="utf-8")
    proj = Project.load(root)

    real_dump = fm.json.dump

    def _dies(payload, fh, **kw):
        fh.write('{"schema_version": 2, "name": "P", "cur')
        raise OSError("the disk filled up here")

    monkeypatch.setattr(fm.json, "dump", _dies)
    with pytest.raises(OSError):
        proj.save_manifest()
    monkeypatch.setattr(fm.json, "dump", real_dump)

    kept = json.loads((root / "project.json").read_text(encoding="utf-8"))
    assert kept["runs"] == ["run1"] and kept["current_run"] == "run1", (
        "a write that died partway destroyed the manifest it was replacing")
    assert not (root / "project.json.tmp").exists(), (
        "the scratch file was left behind to be mistaken for real data")
