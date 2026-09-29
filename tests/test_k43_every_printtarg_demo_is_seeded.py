"""K43 (Knut, #182 5833695633, 2026-09-25): every demo printtarg lays out is
laid out with a fixed seed.

Knut: *"For the sake of the simulations in the demo package, if they use
printtarg for their layout, then the attribute to use a seed number should be
used. This corresponds to a user having a chart in a verification created for
a run, and printing that for every dated verification run (without
regenerating a chart, which is not supposed to be done anyway)."*

Measured before the change: two unseeded printtarg runs of the same 100-patch
patch set on the same settings placed the patches differently (RANDOM_START
11 against 70; 1,287,288 of 2,175,960 pixels of the page differed). Seeded,
the ``.ti2`` is the same line for line except printtarg's CREATED clock, and
the page image the same except the 247 pixels of the time printed in its
label.

Each test names the mutation it was proved red on.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import make_report_limit_demos as LIMITS                          # noqa: E402
import make_verification_preset_demos as PRESETS                  # noqa: E402

ARGYLL = Path(os.environ.get("CHROMIQ_ARGYLL_BIN", "/Applications/Argyll/bin"))
needs_printtarg = pytest.mark.skipif(
    not (ARGYLL / "printtarg").exists(), reason="ArgyllCMS printtarg is needed")


def test_the_pack_has_one_seed():
    """The demo projects and the demo presets use the same number, the one
    the layout engine's demos use (182).

    MUTATION, proven red: ``PRINTTARG_SEED = 183`` in the presets module."""
    assert LIMITS.PRINTTARG_SEED == PRESETS.PRINTTARG_SEED == 182


def test_every_printtarg_run_of_the_demo_projects_is_seeded():
    """`printtarg_args` is the one place the projects' printtarg command is
    built (grid charts, targen charts, FROM PROFILE GAMUT charts), for both
    instruments the pack uses.

    MUTATION, proven red: drop the ``-R`` from `printtarg_args`."""
    for instrument in ("CM", "i1"):
        args = LIMITS.printtarg_args("A4", instrument)
        i = args.index("-R")
        assert args[i + 1] == str(LIMITS.PRINTTARG_SEED), args
    src = (ROOT / "scripts" / "make_report_limit_demos.py").read_text(
        encoding="utf-8")
    lines = src.splitlines()
    # each printtarg command with the line after it (one call spans two)
    runs = [ln + lines[i + 1] for i, ln in enumerate(lines)
            if 'ARGYLL / "printtarg"' in ln and "run(" in ln]
    assert len(runs) == 3 and all("printtarg_args(" in r for r in runs), runs


def test_the_recorded_settings_carry_the_seed(tmp_path):
    """A chart of the pack opens on the settings it was laid out with, the
    seed among them, so Generate on it places every patch where the printed
    sheet has it.

    MUTATION, proven red: drop ``printtarg-R`` from `record_chart_settings`."""
    from core.file_manager import Run
    folder = tmp_path / "run1"
    folder.mkdir()
    LIMITS.record_chart_settings(folder, "A4")
    got = Run.for_dir(folder).load_meta().create_chart_settings
    assert got["printtarg-R"] == {"enabled": True,
                                  "value": LIMITS.PRINTTARG_SEED}


def test_every_demo_preset_is_saved_with_the_seed():
    """MUTATION, proven red: drop ``printtarg_-R_enabled`` from `payload`."""
    for scale in (1.0, 0.8):
        data = PRESETS.payload(True, scale)
        assert data["printtarg_-R"] == PRESETS.PRINTTARG_SEED
        assert data["printtarg_-R_enabled"] is True


def test_the_presets_window_lays_a_seeded_preset_out_with_its_seed():
    """The page the window judges is the page Generate prints: a preset that
    fixes printtarg's seed is laid out behind the scenes with it, and one
    that does not is laid out without.

    MUTATION, proven red: drop the ``-R`` branch of
    `preset_layout.params_for_user_preset`."""
    from workflow.preset_layout import layout_for_user_preset

    def get(k, d=None):
        return {"argyll_bin_path": str(ARGYLL)}.get(k, d)
    seeded = layout_for_user_preset(PRESETS.payload(True), get)
    argv = seeded["printtarg_argv"]
    assert argv[argv.index("-R") + 1] == "182", argv
    unseeded = dict(PRESETS.payload(True))
    unseeded["printtarg_-R_enabled"] = False
    assert "-R" not in layout_for_user_preset(unseeded, get)["printtarg_argv"]


def _lay_out(folder: Path, chart: Path, args: "list[str]") -> Path:
    folder.mkdir(parents=True)
    shutil.copy2(chart, folder / "chart.ti1")
    subprocess.run([str(ARGYLL / "printtarg"), *args, "chart"], cwd=folder,
                   capture_output=True, text=True, encoding="utf-8",
                   timeout=120, check=True)
    return folder


@needs_printtarg
def test_two_builds_lay_a_chart_out_identically(tmp_path):
    """Two builds of the same chart with the pack's arguments: the same patch
    in the same place, byte for byte, except printtarg's clock (the CREATED
    line of the .ti2, and the time in the page's label).

    MUTATION, proven red: drop the ``-R`` from `printtarg_args` (the
    RANDOM_START and every patch location differ between the two builds,
    printtarg taking its random start from the clock)."""
    from PIL import Image
    chart = tmp_path / "src.ti1"
    PRESETS.write_ti1(chart, PRESETS.chart_page(120))
    args = LIMITS.printtarg_args("A4")
    a = _lay_out(tmp_path / "a", chart, args)
    import time
    time.sleep(1.1)                        # a different second on the clock
    b = _lay_out(tmp_path / "b", chart, args)

    def body(p: Path) -> "list[str]":
        return [ln for ln in p.read_text(encoding="utf-8").splitlines()
                if not ln.startswith("CREATED ")]
    assert body(a / "chart.ti2") == body(b / "chart.ti2")
    tifs = sorted(p.name for p in a.glob("chart*.tif"))
    assert tifs and tifs == sorted(p.name for p in b.glob("chart*.tif"))
    for name in tifs:
        pa = np.asarray(Image.open(a / name))
        pb = np.asarray(Image.open(b / name))
        assert pa.shape == pb.shape
        differ = (pa != pb).any(axis=-1) if pa.ndim == 3 else (pa != pb)
        # the time in the label, a few hundred pixels of a 2-million-pixel page
        assert differ.sum() < 0.001 * differ.size, (name, int(differ.sum()))
