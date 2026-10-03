"""The split-overlay warning outline is adaptive: a patch is flagged only when
it is BOTH above the absolute floor AND an outlier within its own strip (Tukey
fence). This stops a good print being flagged almost everywhere against sRGB
(vivid patches legitimately sit at 30-40+ ΔE), while still catching a genuine
single-patch misread. See #49 (Nelson/pharmacist)."""
from ui.tabs.tab_measure import _strip_outlier_fence
# #182: the floor is two numbers now; the lower (a chart made from a profile)
# is the one these fence cases were written around.
from workflow.patch_flags import ACCURATE_DEFAULT_DE as _PATCH_WARN_DE


def _flags(des, floor=_PATCH_WARN_DE):
    fence = _strip_outlier_fence(des)
    return [d >= floor and d >= fence for d in des]


def test_fence_short_strip_is_zero():
    assert _strip_outlier_fence([10, 20, 30]) == 0.0     # too few to judge spread


def test_saturated_but_clean_strip_flags_nothing():
    # A vivid strip: neutrals low, saturated high — all legitimate vs sRGB.
    des = [3, 5, 9, 15, 22, 28, 33, 38, 41, 12, 7, 25]
    assert not any(_flags(des))                          # no patch is an outlier


def test_single_misread_is_flagged():
    # One patch spikes far above an otherwise ordinary strip → caught.
    des = [3, 5, 9, 12, 7, 15, 8, 62, 11, 6, 14, 9]
    flags = _flags(des)
    assert flags[7] is True and sum(flags) == 1


def test_below_floor_never_flags():
    # A relative outlier that is still small in absolute terms stays quiet.
    des = [1, 1, 2, 1, 2, 1, 9, 1, 2, 1]                  # 9 is an outlier but < floor
    assert not any(_flags(des, floor=_PATCH_WARN_DE))
