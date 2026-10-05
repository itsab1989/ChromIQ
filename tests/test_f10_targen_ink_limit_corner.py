"""F-10 (#182 5985477496): targen 3.5.0's OFPS aborts on an ink-limit corner.

``targen -d4 -l300 -g11`` (the Total Ink Limit row ticked, which pre-fills
300, plus Grey Axis Steps) dies with "ofps: assert, node vertex info should be
empty on add_node2voronoi() entry", so Create Chart fails. ChromIQ now hands
targen the limit + 0.1 in exactly the cases where a fixed patch sits on a
cube corner at that limit, and puts the chosen limit back into the chart.

Found by the profile-engine research. The rule and its measurements are in
``workflow/targen_ink_limit.py``.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.chart_creator import ChartCreator, ChartParams
from workflow.targen_ink_limit import (
    corner_limit, corner_safe_argv, restore_recorded_ink_limit,
)

TARGEN = Path("/Applications/Argyll/bin/targen")

# Every combination reproduced as failing with the stock targen 3.5.0.
REPRODUCED = [
    ["-d4", "-l300", "-g11"],
    ["-d4", "-l300", "-g5"],
    ["-d4", "-l100", "-s11"],
    ["-d4", "-l100", "-m3"],
    ["-d4", "-l200", "-m3"],
    ["-d4", "-l200", "-M3"],
    ["-d4", "-l200", "-m2"],
    ["-d4", "-l300", "-m2"],
    ["-d4", "-l300", "-b2"],
    ["-d2", "-l100", "-s11"],
    ["-d2", "-l200", "-m3"],
    ["-d5", "-l100", "-b3"],
    ["-d5", "-l200", "-M3"],
    ["-d0", "-l100", "-s11"],
]


def _limit(argv: list[str]) -> str:
    for i, a in enumerate(argv):
        if a == "-l":
            return argv[i + 1]
        if a.startswith("-l"):
            return a[2:]
    raise AssertionError("no -l in argv")


@pytest.mark.parametrize("argv", REPRODUCED, ids=" ".join)
def test_every_reproduced_corner_is_nudged_up(argv):
    out, chosen = corner_safe_argv([*argv, "chart"])
    assert chosen == float(_limit(argv))
    assert float(_limit(out)) == pytest.approx(chosen + 0.1)
    # Nothing but the limit changes.
    assert [a for a in out if not a.startswith("-l")] == \
           [a for a in [*argv, "chart"] if not a.startswith("-l")]


@pytest.mark.parametrize("argv", [
    ["-d4", "-l250", "-g11"],
    ["-d4", "-l320", "-g11"],
    ["-d4", "-l299", "-m3"],
    ["-d4", "-l300", "-s11"],          # single-ink steps only reach 100
    ["-d4", "-l300"],                  # no fixed patch on a corner
    ["-d4", "-l400", "-m3"],           # 100 x channels limits nothing
    ["-d2", "-l300", "-g11"],          # likewise for RGB
    ["-d6", "-l200", "-m3"],           # five inks and more: not OFPS
    ["-d4", "-l300", "-g11", "-Q"],    # fast sampler: not OFPS
    ["-d4", "-g11"],                   # no limit at all
    ["-d0", "-l200", "-s11"],
], ids=" ".join)
def test_a_limit_that_is_not_a_corner_is_passed_unchanged(argv):
    out, chosen = corner_safe_argv([*argv, "chart"])
    assert chosen is None
    assert out == [*argv, "chart"]


def test_both_spellings_of_the_limit_are_read():
    """The Total Ink Limit row emits ``-l 300``; the editor emits ``-l300``."""
    out, chosen = corner_safe_argv(["-v", "-d4", "-g11", "-l", "300", "c"])
    assert chosen == 300.0
    assert out == ["-v", "-d4", "-g11", "-l", "300.1", "c"]
    assert corner_limit(["-d4", "-g", "11", "-l300", "c"]) == 300.0


def test_extra_inks_are_counted(tmp_path):
    """-d4 plus one -D ink is five channels, which targen does not OFPS."""
    assert corner_limit(["-d4", "-D", "6", "-l200", "-m3", "c"]) is None
    assert corner_limit(["-d4", "-l200", "-m3", "c"]) == 200.0


def test_the_ti1_gets_the_chosen_limit_back(tmp_path):
    ti1 = tmp_path / "c.ti1"
    ti1.write_text('CTI1\nTOTAL_INK_LIMIT "300.1"\nBEGIN_DATA\nEND_DATA\n',
                   encoding="utf-8")
    assert restore_recorded_ink_limit(ti1, 300.0)
    assert 'TOTAL_INK_LIMIT "300.0"' in ti1.read_text(encoding="utf-8")
    assert not restore_recorded_ink_limit(ti1, 300.0)   # already right


needs_targen = pytest.mark.skipif(not TARGEN.exists(),
                                  reason="ArgyllCMS targen not installed")


def _targen(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([str(TARGEN), *argv], cwd=cwd, capture_output=True, encoding="utf-8", errors="replace",
                          timeout=300, stdin=subprocess.DEVNULL)


@needs_targen
@pytest.mark.parametrize("argv", REPRODUCED, ids=" ".join)
def test_every_reproduced_combination_now_generates(argv, tmp_path):
    base = [*argv[:1], "-f60", "-e0", "-B0", *argv[1:], "chart"]
    out, chosen = corner_safe_argv(base)
    assert chosen is not None
    r = _targen(out, tmp_path)
    assert r.returncode == 0, f"targen still fails with {out}: {r.stderr}"


@needs_targen
def test_the_nudge_keeps_every_grey_step(tmp_path):
    """Why up and not down: at 299.9 targen drops C=M=Y=100, the darkest step."""
    def greys(limit: str) -> int:
        d = tmp_path / limit
        d.mkdir()
        r = _targen(["-d4", "-f0", "-e0", "-B0", "-s0", f"-l{limit}", "-g11", "c"], d)
        assert r.returncode == 0, r.stderr
        rows = (d / "c.ti1").read_text(encoding="utf-8").split("BEGIN_DATA\n")[1]
        return sum(1 for line in rows.splitlines()
                   if line.split()[1:4] == ["100.0000"] * 3)
    assert greys("300.1") == 1
    assert greys("299.9") == 0


# ---------------------------------------------------------------------------
# Create Chart's own path: ChartCreator with the real targen behind it.
# ---------------------------------------------------------------------------

class _RealTargenRunner:
    """Runs targen for real (with a timeout); the engine lays the chart out."""

    def __init__(self) -> None:
        self.argv: list[str] = []
        self.is_running = False

    def run(self, tool, args, cwd, on_line=None, on_finish=None):
        assert tool == "targen", tool
        self.argv = list(args)
        r = _targen(list(args), Path(cwd))
        for line in (r.stdout + r.stderr).splitlines():
            if on_line:
                on_line(line)
        if on_finish:
            on_finish(r.returncode)


class _FileManager:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._project = None

    def project(self):
        from core.file_manager import Project
        if self._project is None:
            self._project = Project.create_or_load(self.root, self.root.name)
        return self._project

    def chart_stem(self, *, cal_target: bool) -> str:
        return self.project().current_run().stem


class _Settings:
    def get(self, key, default=None):
        return True if key == "use_chromiq_layout_engine" else default


def _cmyk_grey_params() -> ChartParams:
    return ChartParams(
        instrument="i1", paper="A4", device_type="4", tiff_dpi=100,
        is_manual=True, patches=80, white_patches=4, black_patches=4,
        grey_steps=11, extra_targen_args="-l 300",
        settings_snapshot={"targen": {"-l": 300}},
    )


@needs_targen
def test_create_chart_with_ink_limit_300_and_grey_steps_generates(tmp_path):
    runner = _RealTargenRunner()
    creator = ChartCreator(runner, _FileManager(tmp_path / "cmyk"), _Settings())
    params = _cmyk_grey_params()
    lines: list[str] = []
    finished: list[list[Path]] = []
    creator.generate(params, on_line=lines.append, on_finish=finished.append)

    assert "300.1" in runner.argv, runner.argv
    assert finished and finished[0], "\n".join(lines[-15:])

    run_dir = tmp_path / "cmyk" / "runs" / "run1"
    ti1 = (run_dir / "cmyk.ti1").read_text(encoding="utf-8")
    assert 'TOTAL_INK_LIMIT "300.0"' in ti1
    assert any(line.split()[1:5] == ["100.0000", "100.0000", "100.0000", "0.00000"]
               for line in ti1.split("BEGIN_DATA\n")[1].splitlines()), \
        "the darkest grey step (C=M=Y=100) must be kept"
    ti2 = (run_dir / "cmyk.ti2").read_text(encoding="utf-8")
    assert "300.1" not in ti2


def test_the_users_setting_and_the_stamp_keep_the_chosen_limit(tmp_path):
    class _NoRun(_RealTargenRunner):
        def run(self, tool, args, cwd, on_line=None, on_finish=None):
            self.argv = list(args)

    runner = _NoRun()
    creator = ChartCreator(runner, _FileManager(tmp_path / "cmyk"), _Settings())
    params = _cmyk_grey_params()
    creator.generate(params, on_line=lambda _l: None, on_finish=lambda _t: None)

    assert "300.1" in runner.argv
    assert params.extra_targen_args == "-l 300"
    assert params.settings_snapshot == {"targen": {"-l": 300}}
    stamp = " ".join(creator.stamp_lines(params, 80))
    assert "-l 300 " in stamp and "300.1" not in stamp


def test_a_limit_of_320_reaches_targen_unchanged(tmp_path):
    class _NoRun(_RealTargenRunner):
        def run(self, tool, args, cwd, on_line=None, on_finish=None):
            self.argv = list(args)

    runner = _NoRun()
    creator = ChartCreator(runner, _FileManager(tmp_path / "cmyk"), _Settings())
    params = _cmyk_grey_params()
    params.extra_targen_args = "-l 320"
    creator.generate(params, on_line=lambda _l: None, on_finish=lambda _t: None)
    i = runner.argv.index("-l")
    assert runner.argv[i + 1] == "320"
    assert creator._ink_limit_restore is None
