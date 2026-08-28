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
    #: How close to the limit a strip has to be before it is called "close to
    #: the limit", as a percentage of that instrument's own limit (#149, Knut
    #: 2026-08-14). It was a fixed 35%, which is far too wide:
    #:
    #:     *"The typical message is 'Close to the limit - 521 ms per patch …
    #:     (aim for 400 ms or more)'. 521 is more than 30% above 400. This is
    #:     too far away from the limit to say that it is close."*
    #:
    #: He is right — 400 × 1.35 = 540 ms, so his 521 ms sat just inside the old
    #: band. At the 10% default the band is 400–440 ms and 521 ms reads as a
    #: good speed, which is what it deserved. 0 means "never say close to the
    #: limit; only warn when a strip is genuinely too fast".
    marginal_percent: float = 10.0

    @property
    def knows_rate(self) -> bool:
        return self.sample_hz > 0.0

    @property
    def marginal_seconds(self) -> float:
        """The upper edge of the "close to the limit" band, in seconds per
        patch. Equal to the limit itself when the band is 0%."""
        pct = max(0.0, float(self.marginal_percent or 0.0))
        return self.target_seconds * (1.0 + pct / 100.0)

    def strip_target_seconds(self, patches: int) -> "float | None":
        """The shortest acceptable time for a whole strip of *patches*, or None
        when the count is unknown.

        Knut, #149: *"the actual limit relatable is the limit for a full strip,
        which is the 'per patch limit' multiplied by 'the number of patches per
        strip'."* Milliseconds per patch are hard to feel; seconds per strip are
        what a person actually experiences at the instrument.
        """
        if not patches or patches <= 0:
            return None
        return self.target_seconds * patches

    @property
    def target_seconds(self) -> float:
        """The shortest acceptable time for one patch."""
        if self.knows_rate:
            return self.min_samples / self.sample_hz
        return self.min_patch_seconds

    def samples_for(self, seconds: float) -> "int | None":
        """Estimated samples taken in *seconds*, or None when the rate is
        unknown — never a guess dressed up as a measurement.

        Rounded DOWN: a patch that had time for 22.7 readings got 22 complete
        ones, not 23. Rounding to nearest let a patch just under the limit be
        reported as meeting it while the verdict — which compares the times
        strictly, as Knut requires (#131, 2026-07-27) — called the same strip
        too fast. The figure shown and the figure judged now agree, and both
        are on the honest side of the limit.
        """
        if not self.knows_rate or seconds <= 0:
            return None
        # The epsilon absorbs float noise only: a 20 ms interval arrives as
        # 0.019999… and would otherwise floor to 3 readings instead of 4.
        return int(seconds * self.sample_hz + 1e-9)


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

    # ---- judging a whole strip at once -------------------------------------
    def strip_timed(self, seconds: float, patches: int) -> StripPace:
        """Judge a strip from its **total** time and patch count.

        This is the path that strip-scanning instruments actually take. They
        hand the whole strip back in one go when the swipe ends, so there are no
        per-patch events to time — the only honest figure available is the mean,
        which is exactly how Knut derived the thresholds in the first place
        (seconds per strip ÷ patches per strip).

        *seconds* must be the time the **scan** took, measured from the
        instrument firing — not from when the strip was offered, which would
        include the user lining the head up and make every strip look slow.
        """
        result = StripPace(patches=patches, elapsed=max(0.0, seconds))
        if patches <= 0 or seconds <= 0:
            return result
        result.mean_seconds = seconds / patches
        result.est_samples = self.config.samples_for(result.mean_seconds)
        target = self.config.target_seconds
        # Strictly on the time, per Knut (#131, 2026-07-27): "the limits shall
        # always be used strictly according to the calculations". A 15-patch
        # strip needs 15 × 23 = 345 readings, 345 ÷ 50 = 6.9 s, so 460 ms for
        # each patch — and 460 ms stays 460 ms whatever the strip's length; it
        # is the strip TOTAL that grows with the patch count.
        # The epsilon is float repair, not leniency: an 11-patch strip's exact
        # minimum is 23 × 11 ÷ 50 = 5.06 s, and 5.06 ÷ 11 lands a whisker under
        # 0.46 in binary, so the exactly-correct strip would be called too fast.
        result.too_fast = result.mean_seconds < target * (1 - 1e-9)
        result.marginal = (not result.too_fast
                           and result.mean_seconds < self.config.marginal_seconds)
        return result

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
                               and result.mean_seconds < self.config.marginal_seconds)
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
def strip_limit_phrase(config: PaceConfig, patches: int) -> str:
    """"400 ms or more per patch — 6.0 sec. or more per strip", or just the
    per-patch half when the strip length is unknown.

    Knut asked for the whole-strip figure because milliseconds per patch are
    hard to relate to (#149), and for it to be kept short because the message
    sits under the preview where width is scarce: *"there is no need mentioning
    how many patches a strip has, as it is visible in the preview"*. Always one
    decimal, and "sec." rather than "seconds", both his ruling.
    """
    from core.i18n import tr
    target_ms = int(round(config.target_seconds * 1000))
    strip_s = config.strip_target_seconds(patches)
    if strip_s is None:
        return tr("{target} ms or more per patch").format(target=target_ms)
    return tr("{target} ms or more per patch — {secs} sec. or more per strip"
              ).format(target=target_ms, secs=f"{strip_s:.1f}")


def strip_limit_fact(config: PaceConfig, patches: int) -> str:
    """The same limit stated as a fact rather than an instruction, for a strip
    that was read well — "aim for 400 ms" reads oddly at someone already doing
    better than that."""
    from core.i18n import tr
    target_ms = int(round(config.target_seconds * 1000))
    strip_s = config.strip_target_seconds(patches)
    if strip_s is None:
        return tr("The limit is {target} ms per patch").format(target=target_ms)
    return tr("The limit is {target} ms per patch — {secs} sec. per strip"
              ).format(target=target_ms, secs=f"{strip_s:.1f}")


def measured_phrase(pace: StripPace) -> str:
    """"415 ms per patch, roughly 20 readings each" — the sample count only
    when the instrument's rate is known, never a guess dressed as a fact."""
    from core.i18n import tr
    ms = int(round(pace.mean_seconds * 1000))
    if pace.est_samples is None:
        return tr("{ms} ms per patch").format(ms=ms)
    return tr("{ms} ms per patch, roughly {n} readings each").format(
        ms=ms, n=pace.est_samples)


def strip_pace_message(pace: StripPace, config: PaceConfig) -> str:
    """A friendly sentence about a finished strip, or "" when it read fine.

    Speaks in seconds always, and adds the estimated sample count only when the
    instrument's rate is known — never implying a precision we do not have.
    """
    from core.i18n import tr
    if pace.patches <= 1 or not (pace.too_fast or pace.marginal):
        return ""
    measured = measured_phrase(pace)
    if pace.too_fast:
        return tr(
            "That strip was read quickly: {measured}. Aim for {limit}. A "
            "slower, steadier swipe gives the instrument more light to work "
            "with, and is read more accurately."
        ).format(measured=measured,
                 limit=strip_limit_phrase(config, pace.patches))
    return tr(
        "That strip read fine, but it was close to the limit: {measured}. "
        "{limit}. A slightly slower swipe leaves more margin, so fewer strips "
        "need reading twice."
    ).format(measured=measured,
             limit=strip_limit_fact(config, pace.patches))


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
    "i1pro3":         (400.0,   33),
    "i1pro3plus":     (400.0,   66),   # 16 mm minimum patch, so fewer per strip
    # 20, not X-Rite's implied ~34: Knut's practical tests (#131 2026-07-27)
    # show the ColorMunki reads a strip well at 5-6 s where the vendor figures
    # imply 7.5 s, and still builds good profiles. Settled at 20 with the
    # per-instrument strip lengths below (#130, 2026-07-29).
    "colormunki":     ( 50.0,   20),   # slowest; needs long patches
    "spectroscan":    (250.0, None),   # motorised — no pace to judge
    # The CR30 is placed on one patch by hand and triggered by its own button
    # (#159). Like the SpectroScan there is no swipe, so the threshold is None
    # (shown as "Off") and no pace warning is ever raised. The rate is inert in
    # both directions: nothing subscribes to patch events for pace
    # (tab_measure.py:1016-1022 — the pace model is wired to strip_measured
    # only, and a CR30 never emits a strip), and the CR30 does not stream
    # samples at all. It is 100.0 rather than 0 or 1 purely so the Preferences
    # spinbox shows the shipped default instead of silently clamping it to the
    # bottom of SAMPLE_HZ_RANGE (10-500). The row exists so that
    # _pace_config's unknown-instrument fallback — the i1Pro's (100.0, 20) —
    # can never be applied to a CR30 chart.
    "cr30":           (100.0, None),
}

#: How many patches one strip of a typical chart holds, per instrument (Knut,
#: #130 2026-07-29). Used **only** for the "min. strip reading speed" figure
#: shown beside each instrument in Preferences → Measurement: it turns the two
#: settings on that row into the seconds a strip of that length may not be read
#: faster than. It changes nothing about how a measurement is judged.
#:
#: It is per instrument because strip length follows the instrument's smallest
#: usable patch: an i1Pro 3 Plus needs 16 mm patches and so fits half as many
#: on a strip as an i1Pro 2. ``None`` means "not applicable" — the SpectroScan
#: is a motorised table and reads patch by patch, so a strip length says
#: nothing about it.
ESTIMATE_PATCHES = {
    "i1pro":          25,
    "i1pro2":         25,
    "i1pro3":         30,
    "i1pro3plus":     15,
    "colormunki":     15,
    "spectroscan":    None,
    "cr30":           None,   # no strips at all — shown as "N/A" (#159)
}

#: What a user may enter for the strip length. 0 shows as "N/A".
ESTIMATE_PATCHES_RANGE = (0, 200)


def estimate_patches_for(key):
    """Patches per strip for a model key, or ``None`` when not applicable.

    An unrecognised instrument borrows the i1Pro's strip length for the same
    reason :func:`defaults_for` borrows its rate — a figure has to come from
    somewhere, and the conservative one is the right one to guess with.
    """
    if key in ESTIMATE_PATCHES:
        return ESTIMATE_PATCHES[key]
    return ESTIMATE_PATCHES["i1pro"]

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
    # Not an ArgyllCMS instrument: Argyll never opens a CR30, ChromIQ does
    # (#159). The row is here so that a model string ChromIQ reports for itself
    # resolves to the CR30's own defaults rather than the i1Pro fallback.
    ("cr30", "cr30"),
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


# ---------------------------------------------------------------------------
# Why a strip failed (Knut, #131 2026-07-26)
# ---------------------------------------------------------------------------
#: ArgyllCMS reports a failed strip with a driver message, and the wording is
#: identical across the ColorMunki, i1Pro, i1Pro 2 and i1Pro 3 families (their
#: ``interp_error`` tables carry the same strings). Only some of those failures
#: mean "you swiped too fast", and telling the user to slow down when they did
#: not is worse than saying nothing — so each message is classified.
#:
#: TOO FAST — the scan did not gather enough light or enough samples:
_TOO_FAST = (
    "not enough samples per patch",   # Argyll says "Slow Down!" itself
    "reading is too short",           # the whole swipe was over too quickly
    "not enough patches",             # patches too short in samples to resolve
)
#: TOO SLOW / hesitant — extra transitions were found, so "slow down" would be
#: exactly the wrong advice:
_TOO_SLOW = (
    "too many patches",
)
#: NOT about pace at all — position, light level or calibration:
_NOT_PACE = (
    "swipe didn't start and end on the media",
    "light level is too low",
    "light level is too high",
    "white reference calibration",
    "no refresh rate",
    "no delay calibration transition",
    "no flashes recognized",
    "no ambient found",
)


def failure_kind(detail: str) -> str:
    """Classify a strip failure as ``"too_fast"``, ``"too_slow"``, ``"other"``.

    "Reading is inconsistent" deliberately lands in *other*: it means the swipe
    was uneven rather than simply quick, and blaming speed for it would send the
    user in a direction that may not help.
    """
    low = (detail or "").lower()
    for needle in _TOO_FAST:
        if needle in low:
            return "too_fast"
    for needle in _TOO_SLOW:
        if needle in low:
            return "too_slow"
    for needle in _NOT_PACE:
        if needle in low:
            return "other"
    return "other"


def failure_advice(detail: str, config: "PaceConfig") -> str:
    """A sentence about *why* a strip failed, in terms of the thresholds
    currently set in Preferences — never a fixed number, so changing a setting
    changes what the user is told (Knut, #131)."""
    from core.i18n import tr
    kind = failure_kind(detail)
    target_ms = int(config.target_seconds * 1000)
    if kind == "too_fast":
        if config.knows_rate:
            return tr(
                "That reading was too quick for the instrument to gather what "
                "it needs. Aim for at least {ms} ms on each patch — that is the "
                "{n} readings per patch set for this instrument in Preferences "
                "→ Measurement, at {hz} readings per second."
            ).format(ms=target_ms, n=config.min_samples, hz=int(config.sample_hz))
        return tr(
            "That reading was too quick for the instrument to gather what it "
            "needs. Aim for at least {ms} ms on each patch."
        ).format(ms=target_ms)
    if kind == "too_slow":
        return tr(
            "More patches were found than the strip holds, which usually means "
            "the swipe hesitated or wavered rather than being too quick. Try "
            "one smooth, even movement from the start of the strip to the end.")
    return tr(
        "This one does not look like a speed problem. Check that the swipe "
        "starts before the first patch and ends after the last, stays on the "
        "strip, and that the instrument is flat on the paper.")


def _target_ms(key) -> int:
    """The slowest-acceptable patch time these defaults imply, in ms."""
    hz, min_samples = defaults_for(key)
    if not hz or not min_samples:
        return 0
    return round(min_samples / hz * 1000)


def _calculation_note(key) -> str:
    """How the three numbers on an instrument's row work together.

    This used to be the tooltip of a single common "No. of patches per strip"
    box below the table. Knut moved the strip length onto each instrument's own
    row (#130, 2026-07-29) — *"the information in the help icon text for this
    common parameter should then be added to each of the instruments help text
    icon, informing in the text how each of the three calculation values are
    used"* — so the explanation now travels with the row it describes, worked
    through with that instrument's own figures.
    """
    from core.i18n import tr
    hz, min_samples = defaults_for(key)
    patches = estimate_patches_for(key)
    head = tr(
        "\n\nHOW THE THREE NUMBERS ON THIS ROW ARE USED\n"
        "The figure at the end of the row answers one question: with the "
        "settings on this row, what is the fastest a strip may be read before "
        "ChromIQ says you were quick?\n\n"
        "  patches per strip × minimum readings per patch = readings the strip "
        "needs\n"
        "  readings the strip needs ÷ readings per second = seconds the strip "
        "needs\n\n"
        "•  Readings per second is the instrument's own sampling rate, from its "
        "specification. It rarely needs touching.\n"
        "•  Patches per strip is how many patches one strip of your charts "
        "holds. It is used for the figure at the end of the row and for nothing "
        "else — it changes nothing about how you measure.\n"
        "•  Minimum readings per patch is the limit itself: read a patch faster "
        "than this while measuring and ChromIQ mentions it.")
    if not min_samples or not patches or not hz:
        return head + tr(
            "\n\nOn this row the minimum is Off and no strip length applies, so "
            "nothing is judged and no speed is shown. Set a minimum above Off, "
            "and a number of patches per strip, and this instrument is judged "
            "like any other.")
    readings = patches * min_samples
    return head + tr(
        "\n\nWith the values ChromIQ starts this row with — {patches} patches "
        "per strip, {n} readings per patch, {hz} readings per second — a strip "
        "needs {patches} × {n} = {readings} readings, and {readings} ÷ {hz} = "
        "{secs} seconds. Set the patches per strip to the length of a strip on "
        "your own charts and the figure follows as you type, so a minimum can "
        "be chosen by the reading speed it implies rather than worked out on "
        "paper."
    ).format(patches=patches, n=min_samples, hz=int(hz), readings=readings,
             secs=f"{readings / hz:.1f}")


def explanation_for(key) -> "tuple[str, str]":
    """``(title, body)`` explaining where an instrument's two defaults come
    from, and how they were worked out (Knut, #131 2026-07-26).

    Every figure below is Knut's own derivation, and every one is recomputed
    from :data:`MODEL_DEFAULTS` where it can be, so the explanation can never
    drift away from the values ChromIQ actually ships.
    """
    from core.i18n import tr
    hz, min_samples = defaults_for(key)
    rate = int(hz)
    target = _target_ms(key)
    closing = tr(
        "\n\nWith {n} readings at {hz} readings per second, one patch has to "
        "last at least {ms} ms. Read a strip faster than that and ChromIQ "
        "mentions it; read it at a comfortable pace and it says nothing."
    ).format(n=min_samples, hz=rate, ms=target) if min_samples else ""

    if key == "i1pro":
        return tr("i1Pro (first generation)"), tr(
            "The first i1Pro takes 100 readings per second — half the rate of "
            "the i1Pro 2. It gathers half as much light in the same time, so "
            "the same chart simply needs reading about twice as slowly.\n\n"
            "Worked out from a chart, rather than picked: where an i1Pro 2 "
            "wants about 3 seconds for a strip, this one wants about 6. Six "
            "seconds at 100 readings per second is 600 readings for the whole "
            "strip. A tightly packed i1Pro chart carries around 29 patches per "
            "strip, so 600 ÷ 29 ≈ 20 readings for each patch."
        ) + closing + _calculation_note(key)
    if key == "i1pro2":
        return tr("i1Pro 2"), tr(
            "The i1Pro 2 takes 200 readings per second.\n\n"
            "Worked out from a chart: a slightly hurried strip read in 2.5 "
            "seconds collects 500 readings, and a tightly packed chart carries "
            "27 to 29 patches per strip — 500 ÷ 29 ≈ 17 readings per patch, "
            "which is a little thin. Taking 3 seconds as the sensible minimum "
            "instead gives 3 × 200 = 600 readings, and 600 ÷ 29 ≈ 20 readings "
            "for each patch."
        ) + closing + _calculation_note(key)
    if key == "i1pro3":
        return tr("i1Pro 3"), tr(
            "The i1Pro 3 takes 400 readings per second — twice the i1Pro 2's "
            "rate. That can be spent two ways: reading twice as fast for the "
            "same quality, or reading at the same speed for better quality. "
            "ChromIQ's default spends it on quality, because below roughly two "
            "seconds per strip a human hand grows unsteady and the errors you "
            "save on light you lose on aim.\n\n"
            "Worked out from a chart: 2.5 seconds at 400 readings per second "
            "is 1000 readings per strip. Over 29 patches that is about 34 "
            "readings each; a very dense chart with 33 patches gives about 30."
        ) + closing + _calculation_note(key)
    if key == "i1pro3plus":
        return tr("i1Pro 3 Plus"), tr(
            "The i1Pro 3 Plus reads at the same 400 readings per second as the "
            "i1Pro 3, but its smallest usable patch is much larger — 16 mm — so "
            "a normal 230 to 235 mm strip holds only 14 or 15 patches instead "
            "of nearly 30. Fewer, longer patches means each one can be given "
            "far more readings at the same hand speed.\n\n"
            "Worked out from a chart: 2.5 seconds at 400 readings per second is "
            "1000 readings, and over 15 patches that is about 66 readings each. "
            "A brisker 2-second strip gives 800 readings, or about 53 each.\n\n"
            "So this instrument asks for the most readings per patch of any of "
            "them, while still being read at about the speed of an i1Pro 2."
        ) + closing + _calculation_note(key)
    if key == "colormunki":
        return tr("ColorMunki / i1Studio"), tr(
            "The ColorMunki takes only 50 readings per second — the slowest "
            "here — so it needs the longest patches and the slowest hand. "
            "X-Rite specify a maximum scan speed of 15 cm per second using "
            "20 mm patches.\n\n"
            "Worked out from a chart: at 20 mm per patch, a 230 mm A4 strip "
            "holds about 11 or 12 patches, and at 15 cm per second it takes at "
            "least 7.5 seconds. That is 7.5 × 50 = 375 readings for the strip, "
            "so 375 ÷ 11 ≈ 34 readings for each patch. A denser 15-patch strip "
            "held to that same quality would need 15 × 34 = 510 readings — "
            "about 10 seconds for one strip.\n\n"
            "Thus, the X-Rite provided limits are very strict and limiting. "
            "Practical tests have shown that this instrument is capable of "
            "better speed performance than this, and still resulting in good "
            "quality profiles. A 5-6 second reading speed, which has proven "
            "doable on a 11 patch strip, will give 5 × 50 readings per second "
            "= 250 samples per strip. Using this on the above 11 patch strip "
            "gives 250 ÷ 11 = 23 readings per patch. For a 15 patch strip this "
            "implies 15 × 23 = 345 readings per strip, and 345 ÷ 50 = approx. "
            "7 seconds reading speed.\n\n"
            "The limit is applied by calculation, never by the rounded figures "
            "above. A 15-patch strip needs 15 × 23 = 345 readings, and "
            "345 ÷ 50 = 6.9 seconds; the strips in these examples come to "
            "about 7 seconds for 15 patches and about 5 seconds for 11, which "
            "are approximations for reading comfort. Note what does and does "
            "not change with a longer strip: the time each patch needs stays "
            "the same, while the time the whole strip needs grows with the "
            "number of patches on it.\n\n"
            "SPACER WIDTH GOES WITH READING SPEED\n"
            "Pushing the ColorMunki further also means thinking about the "
            "spacers on your chart. To notice a spacer at all, at least one "
            "reading has to land inside it while the strip is being scanned. "
            "The minimum readings per patch set above fixes how many readings "
            "a whole strip gets: at 23 readings per patch, a 15-patch strip "
            "gets 345. Spread those over a 230 mm strip and there is a reading "
            "every 230 ÷ 345 = 0.7 mm. Allow 40 to 60 % as a margin and you "
            "arrive at a minimum spacer width of roughly 1.0 to 1.1 mm — the "
            "least that chart can carry and still have its spacers found "
            "reliably. Read faster than the setting allows and the spacers "
            "have to be made wider to match.\n\n"
            "A worked example. A chart with 22 patches per strip, a strip "
            "length of 262 mm, and the minimum set to 15 readings per patch:\n"
            "  • readings per strip: 22 × 15 = 330\n"
            "  • fastest the strip may be read: 330 ÷ 50 = 6.6 seconds\n"
            "  • spacing between readings: 262 ÷ 330 ≈ 0.8 mm\n"
            "  • with the margin: 0.8 × 1.4 = 1.1 and 0.8 × 1.6 = 1.3\n"
            "  • so the spacers need to be about 1.1 to 1.3 mm wide.\n"
            "  • the spacer width you settle on will most likely need "
            "verifying by a test print and read."
        ) + closing + _calculation_note(key)
    if key == "spectroscan":
        return tr("SpectroScan (motorised table)"), tr(
            "The SpectroScan is not swiped by hand at all — a motorised table "
            "places the head on each patch and takes about 1.5 seconds over it, "
            "whatever the chart looks like. There is no pace to get wrong, so "
            "there is nothing worth warning about, and the minimum is set to "
            "Off.\n\n"
            "Its sampling frequency can be set anywhere from 50 to 250 readings "
            "per second, and 250 is the usual setting; that is what the rate "
            "here is for. Should you ever want a remark from this instrument "
            "too, give it a minimum above Off and it will be judged like any "
            "other."
        ) + _calculation_note(key)
    if key == "cr30":
        return tr("CR30 (patch by patch)"), tr(
            "The CR30 is not swiped at all. You place it on one patch, press "
            "the button on the instrument, and it takes that one reading — so "
            "there is no reading speed to get wrong and nothing worth warning "
            "about. The minimum is set to Off, and the strip length shows N/A "
            "because a CR30 chart has no strips.\n\n"
            "This whole row is inert for the CR30: ChromIQ judges reading pace "
            "per strip, and a CR30 measurement never produces one. The row is "
            "shown so you can see that, rather than wonder which figures are "
            "being applied behind your back.\n\n"
            "What DOES take the time is the number of patches. Each one is a "
            "hand placement and a button press of roughly two seconds, so a "
            "full A4 sheet of about 345 patches is a long sitting. Choose the "
            "patch count on the Create Chart tab with that in mind."
        ) + _calculation_note(key)
    return tr("This instrument"), tr(
        "ChromIQ has no measured figures for this instrument, so it is judged "
        "by the slowest rate in the i1Pro family. Assuming a faster instrument "
        "than the one in your hand would let a hurried swipe pass unremarked, "
        "which is the failure that costs you a re-read."
    ) + closing + _calculation_note(key)


def defaults_for(key):
    """``(sample_hz, min_samples)`` for a model key.

    An unknown instrument falls back to the **slowest** rate in the i1Pro family
    (Knut): assuming a faster instrument than the one connected would let a
    too-quick swipe pass unremarked, which is the failure that costs a re-read.
    """
    return MODEL_DEFAULTS.get(key, MODEL_DEFAULTS["i1pro"])


# ---------------------------------------------------------------------------
# End-of-measurement summary (Knut, #131 2026-07-26)
# ---------------------------------------------------------------------------
def _hhmmss(seconds: float) -> str:
    s = max(0, int(round(seconds)))
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def session_summary(times, total_seconds: float, worst: int = 10) -> str:
    """How the whole chart went, for the window that closes a measurement.

    *times* maps a strip's name to ``(seconds, succeeded)``. The summary is
    built only from strips that were actually read: a failed scan has no
    reliable duration to average, and including it would drag the figures
    towards a strip that produced nothing.

    "Worst" means **fastest** — the shortest times are the ones that risk a thin
    reading, which is the whole point of watching the pace.
    """
    from core.i18n import tr
    read = {k: v[0] for k, v in (times or {}).items() if v[1] and v[0] > 0}
    lines = [tr("Total measuring time: {hms}").format(hms=_hhmmss(total_seconds))]
    if not read:
        return lines[0]

    values = sorted(read.values())
    mean = sum(values) / len(values)
    lines.append(tr(
        "Strip reading times — average {avg} s, fastest {fast} s, slowest "
        "{slow} s, over {n} strips."
    ).format(avg=f"{mean:.1f}", fast=f"{values[0]:.1f}",
             slow=f"{values[-1]:.1f}", n=len(values))
        if len(values) > 1 else
        tr("Strip reading time: {avg} s, over one strip.").format(
            avg=f"{mean:.1f}"))

    if len(values) > 1:
        ranked = sorted(read.items(), key=lambda kv: kv[1])[:worst]
        listed = ", ".join(f"{name} {secs:.1f} s" for name, secs in ranked)
        lines.append(tr("Strips with worst reading time: {list}").format(
            list=listed))
    return "\n".join(lines)
