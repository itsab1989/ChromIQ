"""flk1 (2026-10-02): a seeded printtarg layout is the same on every run.

`test_k43_every_printtarg_demo_is_seeded.py::test_two_builds_lay_a_chart_out_
identically` went red in 2 of ~8 full gates: two builds with the same ``-R``
and the same RANDOM_START put patch 1 on B15 and on G3. The cause is in
ArgyllCMS: printtarg never initialises ``cols[i].media`` and its strip-layout
optimiser reads it, so the layout follows whatever the allocator left in that
block. ``core/printtarg_env.py`` has the measurements and the remedy
(``MallocLargeCache=0`` on macOS, so the block is always fresh zeroed pages).

Each test names the mutation it was proved red on.
"""
from __future__ import annotations

import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import make_report_limit_demos as LIMITS                          # noqa: E402
import make_verification_preset_demos as PRESETS                  # noqa: E402

from core import printtarg_env as PE                              # noqa: E402

ARGYLL = Path(os.environ.get("CHROMIQ_ARGYLL_BIN", "/Applications/Argyll/bin"))


def test_macos_gets_the_fresh_large_block_setting():
    """MUTATION, proven red: ``DARWIN_PRINTTARG_ENV = {}``."""
    assert PE.printtarg_env_additions("darwin") == {"MallocLargeCache": "0"}
    # nothing measured elsewhere, so nothing claimed elsewhere
    assert PE.printtarg_env_additions("linux") == {}
    assert PE.printtarg_env_additions("win32") == {}


def test_the_environment_keeps_what_it_was_given(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    env = PE.printtarg_env({"PATH": "/x", "LANG": "de_DE.UTF-8"})
    assert env == {"PATH": "/x", "LANG": "de_DE.UTF-8",
                   "MallocLargeCache": "0"}


def test_printtarg_is_recognised_by_name_or_path():
    assert PE.is_printtarg("printtarg")
    assert PE.is_printtarg("/Applications/Argyll/bin/printtarg")
    assert PE.is_printtarg(Path("C:/Argyll/bin/printtarg.exe"))
    assert not PE.is_printtarg("targen")
    assert not PE.is_printtarg("/Applications/Argyll/bin/chartread")


class _Settings:
    def get(self, key, default=None):
        return False if key == "fast_instrument_connect" else default


def test_the_runner_gives_printtarg_and_only_printtarg_the_setting(
        qapp, monkeypatch):
    """The Create Chart run goes through `ArgyllRunner.run`, which adds what
    `environment_additions` returns (QProcess and PTY paths alike).

    MUTATION, proven red: drop the ``is_printtarg`` branch of
    `ArgyllRunner.environment_additions`."""
    from core.argyll_runner import ArgyllRunner
    monkeypatch.setattr(sys, "platform", "darwin")
    runner = ArgyllRunner(_Settings())
    assert runner.environment_additions("printtarg", None) == {
        "MallocLargeCache": "0"}
    assert runner.environment_additions("targen", None) == {}
    assert runner.environment_additions("chartread", None) == {}


def test_the_presets_window_runs_printtarg_with_it(tmp_path, monkeypatch):
    """MUTATION, proven red: drop ``env=printtarg_env()`` from
    `preset_layout.lay_out_with_printtarg`."""
    from workflow import preset_layout as PL
    monkeypatch.setattr(sys, "platform", "darwin")
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw)
        raise OSError("stand-in printtarg")

    exe = tmp_path / "printtarg"
    exe.write_text("", encoding="utf-8")
    chart = tmp_path / "c.ti1"
    chart.write_text("", encoding="utf-8")
    monkeypatch.setattr(PL, "_printtarg_binary", lambda spec: exe)
    monkeypatch.setattr(PL.subprocess, "run", fake_run)
    PL.lay_out_with_printtarg(chart, {PL.PRINTTARG_ARGV: ["-iCM"]})
    assert (seen.get("env") or {}).get("MallocLargeCache") == "0", seen


def test_the_demo_pack_runs_printtarg_with_it(tmp_path, monkeypatch):
    """MUTATION, proven red: drop the ``env=`` from
    `make_report_limit_demos.run`."""
    import subprocess
    monkeypatch.setattr(sys, "platform", "darwin")
    seen = []

    def fake_run(args, **kw):
        seen.append((Path(args[0]).name, kw.get("env")))
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(LIMITS.subprocess, "run", fake_run)
    LIMITS.run([ARGYLL / "printtarg", "-iCM", "x"], tmp_path, 10)
    LIMITS.run([ARGYLL / "targen", "x"], tmp_path, 10)
    assert seen[0][0] == "printtarg"
    assert seen[0][1]["MallocLargeCache"] == "0"
    assert seen[1] == ("targen", None)    # the other tools are untouched


@pytest.mark.skipif(sys.platform != "darwin",
                    reason="only macOS is measured and covered")
@pytest.mark.skipif(not (ARGYLL / "printtarg").exists(),
                    reason="ArgyllCMS printtarg is needed")
def test_many_builds_at_once_lay_the_chart_out_identically(tmp_path):
    """96 builds of the same seeded chart, 16 at a time, through the pack's
    own `run`: every ``.ti2`` the same apart from printtarg's clock.

    Measured without the remedy on this Mac: 2 to 6 builds of every 48 put
    patch 1 somewhere else (G3 or D3 instead of B15), with no other load; so
    96 builds come out all alike by chance well under 1 % of the time. With
    it: 48 of 48 three times running, and 800 of 800 under 20 CPU hogs.

    MUTATION, proven red: ``DARWIN_PRINTTARG_ENV = {}``."""
    chart = tmp_path / "src.ti1"
    PRESETS.write_ti1(chart, PRESETS.chart_page(120))
    args = [str(a) for a in LIMITS.printtarg_args("A4")]

    def build(i: int) -> str:
        folder = tmp_path / f"b{i}"
        folder.mkdir()
        shutil.copy2(chart, folder / "chart.ti1")
        LIMITS.run([ARGYLL / "printtarg", *args, "chart"], folder, 300)
        body = [ln for ln in (folder / "chart.ti2").read_text(
                    encoding="utf-8").splitlines()
                if not ln.startswith("CREATED ")]
        shutil.rmtree(folder)            # the pages are 2 MB each
        return "\n".join(body)

    with ThreadPoolExecutor(16) as pool:
        bodies = list(pool.map(build, range(96)))
    first_patch = sorted({b.split('\n1 "', 1)[1].split('"', 1)[0]
                          for b in bodies})
    assert len(set(bodies)) == 1, (
        f"{len(set(bodies))} different layouts of one seeded chart; "
        f"patch 1 on {first_patch}")
