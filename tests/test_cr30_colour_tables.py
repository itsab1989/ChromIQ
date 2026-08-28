"""The CR30 illuminant/observer tables must match ArgyllCMS's own.

Our XYZ and Argyll's XYZ meet in the same `.ti3`, so the two must not drift.
The tables in `workflow/cr30/colour.py` are ArgyllCMS 3.5.0's `il_D50` / `il_D65`
(`xicc/xspect.c:244`) sampled at the CR30's 31 wavelengths.

These tests re-derive them from the Argyll source when it is present, and always
check the properties that must hold with or without it.
"""
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from workflow.cr30 import colour as c  # noqa: E402

ARGYLL_SRC = pathlib.Path(
    "/Users/Basti/Downloads/Argyll_V3.5.0_orig/xicc/xspect.c")


def _argyll(name):
    src = ARGYLL_SRC.read_text(errors="replace")
    i = src.index(f"static xspect {name} = {{")
    blk = src[i:i + 3200]
    body = blk[blk.index("{", blk.index("100.0")) + 1:]
    vals = [float(x) for x in re.findall(r"-?\d+\.\d+", body)][:107]
    assert len(vals) == 107, "expected 107 bands, 300-830 nm at 5 nm"
    return [vals[(nm - 300) // 5] for nm in c.WL]


@pytest.mark.skipif(not ARGYLL_SRC.is_file(), reason="Argyll source not present")
@pytest.mark.parametrize("name,ours", [("il_D50", c.D50), ("il_D65", c.D65)])
def test_tables_match_argyll(name, ours):
    theirs = _argyll(name)
    worst = max(abs(a - b) for a, b in zip(theirs, ours))
    assert worst < 1e-6, (
        f"{name} differs from ArgyllCMS by up to {worst:.4f}. Our XYZ and "
        "Argyll's meet in the same .ti3 and must not drift.")


@pytest.mark.skipif(not ARGYLL_SRC.is_file(), reason="Argyll source not present")
def test_the_mutation_lands():
    """A comparison that cannot fail proves nothing. Prove it can."""
    theirs = _argyll("il_D50")
    bad = list(theirs)
    bad[20] += 0.55                      # the exact error the real table had
    assert max(abs(a - b) for a, b in zip(theirs, bad)) > 1e-6


def test_uv_variants_are_not_the_colorimetric_illuminant():
    """`ref/D50_0.0.sp` is the UV-content variant used for FWA work: it is ZERO
    below 440 nm. It was briefly used here as a 'trusted source' and produced a
    white point 1.15 out in X. This pins the reason so nobody retries it."""
    sp = pathlib.Path("/Applications/Argyll/ref/D50_0.0.sp")
    if not sp.is_file():
        pytest.skip("Argyll ref data not installed")
    text = sp.read_text(errors="replace")
    lines = text.splitlines()
    b = next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA")
    e = next(i for i, l in enumerate(lines) if l.strip() == "END_DATA")
    vals = [float(v) for v in " ".join(lines[b + 1:e]).split()]
    assert vals[(400 - 300) // 5] == 0.0, "D50_0.0.sp should be zero at 400 nm"
    assert c.D50[0] > 40.0, "the colorimetric D50 is NOT zero at 400 nm"


def test_perfect_diffuser_is_Y100_and_neutral():
    X, Y, Z = c.spectrum_to_xyz([100.0] * 31)
    assert abs(Y - 100.0) < 1e-9, "Y must be 100 for a perfect diffuser"
    L, a, b = c.spectrum_to_lab([100.0] * 31)
    assert abs(L - 100) < 1e-6 and abs(a) < 1e-6 and abs(b) < 1e-6


def test_no_process_wide_observer_state():
    """Two callers wanting different conditions must not race through a global."""
    assert not hasattr(c, "use_observer")
    a = c.spectrum_to_lab([50.0] * 31, c.D50, "2")
    _ = c.spectrum_to_lab([50.0] * 31, c.D65, "10")
    assert c.spectrum_to_lab([50.0] * 31, c.D50, "2") == a


def test_bad_observer_is_rejected():
    with pytest.raises(ValueError, match="observer must be"):
        c.spectrum_to_xyz([50.0] * 31, c.D50, "7")


def test_profiling_default_is_D50_2deg():
    """Argyll expects D50/2 in a .ti3; the device's own display uses D65/10."""
    assert c.PROFILING_OBSERVER == "2"
    assert c.spectrum_to_xyz([50.0] * 31) == c.spectrum_to_xyz([50.0] * 31,
                                                               c.D50, "2")
