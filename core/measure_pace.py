"""Measurement pace: how fast the instrument is being swiped (#131 Phase 2).

Reading a strip too quickly is the most common cause of a rejected scan. Argyll
notices it — but only *afterwards*, by refusing the strip with "Slow Down!", at
which point the strip has to be read again. This module turns the patch events
that arrive during a read into a live estimate of the pace, so the user can be
told while it still costs them nothing.

**How the sample count is derived** (Knut's method, #131 2026-07-26). The
instrument never reports how many samples it took per patch. But successive
patch completions give the time one patch took, and an instrument samples at a
fixed rate, so::

    samples per patch  ≈  seconds per patch  ×  samples per second

**The one uncertain input is that rate.** ChromIQ does not invent it: with no
rate configured for the instrument, the pace is judged in **time per patch**
alone, which needs no constant and is the same judgement expressed in the units
we can actually measure. Configure a rate for an instrument and the estimated
sample count is reported as well, and the threshold becomes a true
"minimum samples per patch".

Pure Python — no Qt, no instrument access — so every branch is unit-testable
with a synthetic clock.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# A pace judgement is only meaningful once a few patches have been read: the
# first interval of a strip includes the user finding the lead-in.
_MIN_PATCHES_FOR_JUDGEMENT = 3
# Intervals longer than this are treated as a pause (the user stopped, an error
# dialog appeared) rather than a slow patch, so they don't flatter the average.
_PAUSE_SECONDS = 5.0


@dataclass(frozen=True)
class PaceConfig:
    """What "fast enough" means for the instrument in use.

    *sample_hz* is the instrument's sampling rate in samples per second, or 0.0
    when it is not known — in which case *min_patch_seconds* is used directly and
    no sample count is claimed.
    """
    min_samples: int = 8
    sample_hz: float = 0.0
    min_patch_seconds: float = 0.10

    @property
    def knows_rate(self) -> bool:
        return self.sample_hz > 0.0

    @property
    def target_seconds(self) -> float:
        """The shortest acceptable time for one patch."""
        if self.knows_rate:
            return self.min_samples / self.sample_hz
        return self.min_patch_seconds

    def samples_for(self, seconds: float) -> "int | None":
        """Estimated samples taken in *seconds*, or None when the rate is
        unknown — never a guess dressed up as a measurement."""
        if not self.knows_rate or seconds <= 0:
            return None
        return round(seconds * self.sample_hz)


@dataclass(frozen=True)
class PatchPace:
    """One patch's contribution to the pace."""
    seconds: float
    est_samples: "int | None"
    too_fast: bool


@dataclass
class StripPace:
    """A finished strip, summarised."""
    patches: int = 0
    elapsed: float = 0.0
    mean_seconds: float = 0.0
    est_samples: "int | None" = None
    too_fast: bool = False
    marginal: bool = False          # passed, but close to the limit


@dataclass
class PaceTracker:
    """Turns patch-completion timestamps into pace judgements.

    Feed it :meth:`patch_completed` with a monotonic timestamp per patch; call
    :meth:`strip_finished` when the strip ends. It keeps no Qt state and no
    history beyond the current strip.
    """
    config: PaceConfig = field(default_factory=PaceConfig)
    _last: "float | None" = None
    _intervals: list[float] = field(default_factory=list)
    _strip_start: "float | None" = None
    _patches: int = 0        # patches READ, which is not intervals + 1 once a
                             # pause has been discarded

    # ---- feeding -----------------------------------------------------------
    def strip_started(self, when: float) -> None:
        self._strip_start = when
        # NOT `_last = when`: the gap between the strip starting and the first
        # patch completing is the user placing the instrument on the lead-in,
        # not the time a patch took. Counting it would make every strip look
        # slower than it was.
        self._last = None
        self._patches = 0
        self._intervals.clear()

    def patch_completed(self, when: float) -> "PatchPace | None":
        """Record a patch. Returns its pace, or None for the first patch of a
        strip (there is no interval yet) and for a pause."""
        prev, self._last = self._last, when
        self._patches += 1
        if self._strip_start is None:
            self._strip_start = when
        if prev is None:
            return None
        seconds = when - prev
        if seconds <= 0 or seconds > _PAUSE_SECONDS:
            return None                      # a pause is not a fast swipe
        self._intervals.append(seconds)
        return PatchPace(
            seconds=seconds,
            est_samples=self.config.samples_for(seconds),
            too_fast=seconds < self.config.target_seconds,
        )

    # ---- judging -----------------------------------------------------------
    @property
    def enough_data(self) -> bool:
        return len(self._intervals) >= _MIN_PATCHES_FOR_JUDGEMENT

    def strip_finished(self, when: "float | None" = None) -> StripPace:
        """Summarise the strip just read, and reset for the next one."""
        result = StripPace(patches=self._patches)
        if self._intervals:
            result.mean_seconds = sum(self._intervals) / len(self._intervals)
            result.est_samples = self.config.samples_for(result.mean_seconds)
            target = self.config.target_seconds
            result.too_fast = self.enough_data and result.mean_seconds < target
            # "Marginal" = it passed, but a little slower and it would not have.
            result.marginal = (self.enough_data and not result.too_fast
                               and result.mean_seconds < target * 1.35)
        if when is not None and self._strip_start is not None:
            result.elapsed = max(0.0, when - self._strip_start)
        elif self._intervals:
            result.elapsed = sum(self._intervals)
        self._last = None
        self._strip_start = None
        self._patches = 0
        self._intervals.clear()
        return result


# ---------------------------------------------------------------------------
# plain-language wording (the UI never formats these itself)
# ---------------------------------------------------------------------------
def strip_pace_message(pace: StripPace, config: PaceConfig) -> str:
    """A friendly sentence about a finished strip, or "" when it read fine.

    Speaks in seconds always, and adds the estimated sample count only when the
    instrument's rate is known — never implying a precision we do not have.
    """
    from core.i18n import tr
    if pace.patches <= 1 or not (pace.too_fast or pace.marginal):
        return ""
    per_patch = tr("{ms} ms per patch").format(ms=int(pace.mean_seconds * 1000))
    if pace.est_samples is not None:
        per_patch = tr("{ms} ms per patch — roughly {n} samples").format(
            ms=int(pace.mean_seconds * 1000), n=pace.est_samples)
    target_ms = int(config.target_seconds * 1000)
    if pace.too_fast:
        return tr(
            "That strip was read quickly: {measured}. Aim for at least {target} "
            "ms per patch — a slower, steadier swipe gives the instrument more "
            "light to work with, and is read more accurately."
        ).format(measured=per_patch, target=target_ms)
    return tr(
        "That strip read fine, but it was close to the limit: {measured}. A "
        "slightly slower swipe leaves more margin, so fewer strips need reading "
        "twice."
    ).format(measured=per_patch)


# ---------------------------------------------------------------------------
# Per-model sampling rates and thresholds (Knut, #131 2026-07-26)
# ---------------------------------------------------------------------------
#: Scanning measurement frequency in samples per second, and the minimum
#: samples per patch that model needs for a dependable read. Both are Knut's
#: figures — the rates from the manufacturers' specifications, the thresholds
#: derived from real patch densities and the reading speeds a person can
#: actually hold. ``None`` for a threshold means **no pace warning** for that
#: instrument.
#:
#: The SpectroScan is a motorised table: it places the head on each patch and
#: takes about 1.5 s regardless, so there is no swipe to be too quick and no
#: threshold worth setting.
MODEL_DEFAULTS = {
    # model key      sample_hz   min samples per patch
    "i1pro":          (100.0,   20),   # Rev A — half the Pro 2's rate
    "i1pro2":         (200.0,   20),
    "i1pro3":         (400.0,   30),
    "i1pro3plus":     (400.0,   60),   # 16 mm minimum patch, so fewer per strip
    "colormunki":     ( 50.0,   30),   # slowest; needs long patches
    "spectroscan":    (250.0, None),   # motorised — no pace to judge
}

#: What a user may enter, per Knut: rates 10-500 Hz, thresholds 10-100 samples
#: (or off).
SAMPLE_HZ_RANGE = (10.0, 500.0)
MIN_SAMPLES_RANGE = (10, 100)

#: ArgyllCMS instrument names (``inst_name(itype)``) -> our model key. Argyll
#: distinguishes the i1Pro generations even though a chart records only the
#: family, so the connected model can be identified at read time. Most specific
#: patterns first, so "i1 Pro3+" is never mistaken for "i1 Pro".
_ARGYLL_MODEL_KEYS = (
    ("i1 pro3+", "i1pro3plus"),
    ("i1pro3+", "i1pro3plus"),
    ("i1 pro3", "i1pro3"),
    ("i1pro3", "i1pro3"),
    ("i1 pro2", "i1pro2"),
    ("i1pro2", "i1pro2"),
    ("i1 pro", "i1pro"),
    ("i1pro", "i1pro"),
    ("colormunki", "colormunki"),
    ("i1studio", "colormunki"),
    ("spectroscan", "spectroscan"),
)


def model_key(argyll_name):
    """Map an ArgyllCMS instrument name to a model key, or None if unrecognised."""
    if not argyll_name:
        return None
    low = argyll_name.lower()
    for needle, key in _ARGYLL_MODEL_KEYS:
        if needle in low:
            return key
    return None


def defaults_for(key):
    """``(sample_hz, min_samples)`` for a model key.

    An unknown instrument falls back to the **slowest** rate in the i1Pro family
    (Knut): assuming a faster instrument than the one connected would let a
    too-quick swipe pass unremarked, which is the failure that costs a re-read.
    """
    return MODEL_DEFAULTS.get(key, MODEL_DEFAULTS["i1pro"])
