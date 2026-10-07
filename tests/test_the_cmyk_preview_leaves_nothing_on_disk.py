"""Beta 12: the CMYK colorimetric preview leaves nothing on disk, not even
after a crash.

``workflow/colorimetric_preview.py`` kept cctiff's converted pages in a
temporary folder for the whole session and removed it at quit, so a crash or a
Force Quit left it behind. The converted pages are now held in memory; cctiff's
folder lives only for the call, carries the process id, and a folder left by a
ChromIQ killed in the middle of a call is swept by the next one, exactly as the
RGB preview does (review C of beta 12).

Proved here with real processes and SIGKILL, not with a mock of the cleanup.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

import pytest

from tests.argyll_env import argyll_bin_dir, argyll_tool
from workflow import colorimetric_preview as CP

REPO = Path(__file__).resolve().parent.parent
GENERIC_CMYK = Path("/System/Library/ColorSync/Profiles/Generic CMYK Profile.icc")
live = pytest.mark.skipif(
    argyll_tool("cctiff") is None or not GENERIC_CMYK.exists(),
    reason="ArgyllCMS or Generic CMYK profile not installed")
posix = pytest.mark.skipif(os.name == "nt", reason="SIGKILL is POSIX")


def _ours(root: Path) -> "list[Path]":
    return sorted(root.glob(CP._TMP_PREFIX + "*"))


def _child_env(tmp_root: Path) -> dict:
    env = dict(os.environ)
    env["TMPDIR"] = str(tmp_root)          # the child's tempfile root
    env["PYTHONPATH"] = str(REPO)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    return env


def _cmyk_page(folder: Path) -> Path:
    import workflow.ti2_relayout as R
    from workflow.layout_engine import chart as eng_chart
    rows = [((0.0, 0.0, 0.0, 0.0), None), ((100.0, 0.0, 0.0, 0.0), None),
            ((0.0, 100.0, 0.0, 0.0), None), ((0.0, 0.0, 0.0, 100.0), None)]
    ti1 = R.write_ti1_nchannel("CMYK", ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"],
                               rows, folder / "c.ti1")
    res = eng_chart.build_chart(str(ti1), folder / "c", seed=1, dpi=72)
    return Path((res.tiff_paths or [None])[0])


def test_a_conversion_leaves_no_folder_and_no_file(tmp_path, monkeypatch):
    """The fake cctiff writes its output where it is told; after the call the
    folder is gone and the pages are in memory."""
    from PIL import Image
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(CP, "_swept", True)
    CP._cache.clear()
    bin_dir = tmp_path / "bin"
    (bin_dir).mkdir()
    (bin_dir / "cctiff").write_text("", encoding="utf-8")
    (tmp_path / "ref").mkdir()
    (tmp_path / "ref" / "sRGB.icm").write_bytes(b"x")
    tif = tmp_path / "page.tif"
    tif.write_bytes(b"x")
    prof = tmp_path / "p.icc"
    prof.write_bytes(b"x")
    seen = {}

    def fake(cmd, **kw):
        out = Path(cmd[-1])
        seen["dir"] = out.parent
        assert out.parent.name.startswith(CP._tmp_prefix())
        Image.new("RGB", (4, 3), (10, 20, 30)).save(out)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    frames = CP.colorimetric_rgb_frames(tif, prof, bin_dir, runner=fake)
    assert frames and frames[0].getpixel((0, 0)) == (10, 20, 30)
    assert not seen["dir"].exists()
    assert _ours(tmp_path) == []
    # the frame accessor gives the same page, and a page past the end gives
    # the first, as the preview's old seek() did
    assert CP.colorimetric_rgb_frame(tif, prof, bin_dir, 0, runner=fake) is frames[0]
    assert CP.colorimetric_rgb_frame(tif, prof, bin_dir, 5, runner=fake) is frames[0]
    CP._cache.clear()


def test_the_sweep_takes_only_a_dead_process_folder(tmp_path):
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    orphan = tmp_path / f"{CP._TMP_PREFIX}{dead.pid}-abc"
    live_one = tmp_path / f"{CP._TMP_PREFIX}{os.getpid()}-def"
    unrelated = tmp_path / "chromiq-colorimetric-legacy"      # no pid: not ours to judge
    other = tmp_path / f"chromiq-print-preview-{dead.pid}-x"  # the RGB preview's
    for d in (orphan, live_one, unrelated, other):
        d.mkdir()
        (d / "page.tif").write_bytes(b"x")
    CP._sweep_orphans(tmp_path)
    assert not orphan.exists()
    assert live_one.exists() and unrelated.exists() and other.exists()


@posix
@live
def test_a_chromiq_killed_after_a_real_conversion_leaves_nothing(tmp_path):
    """A real cctiff conversion in a child process, then SIGKILL (no atexit,
    no finaliser runs): the temporary root holds no folder of ours."""
    page = _cmyk_page(tmp_path)
    root = tmp_path / "tmproot"
    root.mkdir()
    script = textwrap.dedent(f"""
        import sys, time
        from workflow import colorimetric_preview as CP
        frames = CP.colorimetric_rgb_frames({str(page)!r}, {str(GENERIC_CMYK)!r},
                                            {str(argyll_bin_dir())!r})
        print("converted", bool(frames), flush=True)
        time.sleep(600)
    """)
    p = subprocess.Popen([sys.executable, "-c", script], env=_child_env(root),
                         stdout=subprocess.PIPE, text=True)
    try:
        line = p.stdout.readline()
        assert line.strip() == "converted True", line
        os.kill(p.pid, signal.SIGKILL)
        p.wait(timeout=60)
    finally:
        if p.poll() is None:
            p.kill()
    assert p.returncode == -signal.SIGKILL
    assert _ours(root) == [], _ours(root)


@posix
def test_a_chromiq_killed_during_a_conversion_is_swept_by_the_next(tmp_path):
    """Killed in the middle of the cctiff call, the folder stays (nothing can
    run in a SIGKILLed process); the next ChromIQ's first conversion removes
    it, because its process is gone."""
    root = tmp_path / "tmproot"
    root.mkdir()
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "cctiff").write_text("", encoding="utf-8")
    (tmp_path / "ref").mkdir()
    (tmp_path / "ref" / "sRGB.icm").write_bytes(b"x")
    (tmp_path / "page.tif").write_bytes(b"x")
    (tmp_path / "p.icc").write_bytes(b"x")
    script = textwrap.dedent(f"""
        import time
        from pathlib import Path
        from workflow import colorimetric_preview as CP

        def hang(cmd, **kw):
            Path(cmd[-1]).write_bytes(b"half a page")
            print("in cctiff", flush=True)
            time.sleep(600)

        CP.colorimetric_rgb_frames({str(tmp_path / "page.tif")!r},
                                   {str(tmp_path / "p.icc")!r},
                                   {str(tmp_path / "bin")!r}, runner=hang)
    """)
    p = subprocess.Popen([sys.executable, "-c", script], env=_child_env(root),
                         stdout=subprocess.PIPE, text=True)
    try:
        assert p.stdout.readline().strip() == "in cctiff"
        os.kill(p.pid, signal.SIGKILL)
        p.wait(timeout=60)
    finally:
        if p.poll() is None:
            p.kill()
    left = _ours(root)
    assert len(left) == 1 and left[0].name.startswith(f"{CP._TMP_PREFIX}{p.pid}-")

    # the next ChromIQ: its first conversion sweeps, before anything else
    nxt = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(f"""
            import subprocess
            from workflow import colorimetric_preview as CP
            CP.colorimetric_rgb_frames(
                {str(tmp_path / "page.tif")!r}, {str(tmp_path / "p.icc")!r},
                {str(tmp_path / "bin")!r},
                runner=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, b"", b""))
        """)], env=_child_env(root), timeout=120)
    assert nxt.returncode == 0
    assert _ours(root) == [], _ours(root)
