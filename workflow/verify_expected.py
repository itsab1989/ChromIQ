"""The expected colour of a verification patch while it is measured (#182).

Approved by Knut on #182 (questions of 5963902307, answered in 5964173774 and
5964384250):

1. A verification chart ChromIQ printed is judged, patch by patch while it is
   read, against **the run profile's own prediction** of the ink values that
   were really sent to the printer (forward table, absolute colorimetric), at
   its own limit, "a verification judged against its profile" (ΔE 10 by
   default since beta 11, Knut 5983470377; before, the "chart made from a
   profile" limit, ΔE 30). Today's sRGB
   estimate at the other limit (ΔE 95) stays the fallback.
2. The fallback is also taken for a profile built under another light: an
   illuminant other than D50 (colprof ``-i``), another observer (``-o``) or
   FWA compensation (``-f``). Such a profile predicts colours under that
   light, and chartread always measures D50.
3. On these charts the strip outlier test is ignored, whatever the user's
   setting: every patch past the limit is outlined, even if the whole strip
   is off.

This is ArgyllCMS's own design, done afterwards: ``targen -c <profile>`` writes
the profile's prediction into the chart and marks it
``ACCURATE_EXPECTED_VALUES``, and chartread then warns at 30 instead of 95.

WHAT WAS SENT is the whole difficulty, and the print record answers it
(``workflow/verification_print.py``, A15-A18 and B7):

* **raw**: the ``.ti2``'s own RGB went to the printer unchanged;
* **through the profile**: the page was converted with cctiff, so the values
  sent are cctiff's output for the chart's RGB through exactly the chain the
  print used (:func:`workflow.cctiff_apply.convert_args`: the recorded source
  profile and intent, then the profile). The ``.ti2`` RGB is never what was
  printed on such a sheet, and predicting it would compare the sheet with a
  colour nobody asked for;
* **a printer calibration** (``-K``): the profile describes the printer behind
  the calibration, so the prediction is taken BEFORE the ``.cal`` when the
  profile was built from a chart printed with that same calibration (the
  record's SHA-1 against the run's own). Otherwise the values actually sent,
  calibration included, or the fallback when that cannot be known.

Phase 1 is Python only (the challenge of 2026-10-03, CHALLENGE_NOTES §5): no
engine change, no change to the ``.ti2``, nothing new written at print time.
The engine still compares against the ``.ti2``; the Measure tab replaces the
expected colour of every patch event with the prediction and recomputes the
ΔE with :func:`workflow.measurement_report.engine_patch_de`, and the repaint
from disk (UMM 10.6) does exactly the same through
:func:`apply_expected`.

Process model: ``subprocess.run`` with an injectable ``runner``, the
``xicclu_runner`` house pattern; never the ArgyllRunner singleton (a
measurement is about to use it), and always with a ``timeout=``.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Mapping

from core.logger import get_logger

log = get_logger(__name__)

#: The two answers.
SOURCE_PREDICTION = "prediction"
SOURCE_ESTIMATE = "estimate"

#: cctiff on a one-row image of a few hundred patches takes a tenth of a
#: second; a loaded machine running the gate can take fifty times longer. Two
#: minutes says "did not finish", never "slow" (CLAUDE.md: budget for the
#: loaded machine).
_TIMEOUT_S = 120
#: Cap for the calls made while the window waits (session start, repaint).
_GUI_TIMEOUT_S = 20

#: Build Profile settings that make the forward table predict colour under
#: another light (Knut, #182 5964173774, answer 2). Manual and Guided keep
#: their own copies; either one set counts, because which of the two built
#: the profile is not recorded (the safe direction: fall back).
_ILLUMINANT_KEYS = ("illuminant", "g_illuminant")
_OBSERVER_KEYS = ("observer", "g_observer")
_FWA_KEYS = ("fwa_enabled", "g_fwa_enabled")
#: Values that mean "colprof's default": no ``-i`` / ``-o`` at all.
_DEFAULT_ILLUMINANTS = ("", "D50")
_DEFAULT_OBSERVERS = ("", "1931_2")


@dataclass(frozen=True)
class LiveExpected:
    """Where the expected colour of every patch of one chart comes from.

    *source* is :data:`SOURCE_PREDICTION` or :data:`SOURCE_ESTIMATE`;
    *reason* is one English sentence for the log saying why; *by_loc* maps a
    patch location (``SAMPLE_LOC``, the key every engine event carries) to
    the predicted XYZ on the ``.ti3`` scale (Y of a perfect white = 100,
    absolute D50), empty for the estimate.
    """
    source: str
    reason: str
    by_loc: Mapping[str, tuple] = field(default_factory=dict)
    route: str = ""            # "raw" or "through-profile", for the log
    #: The estimate because the run's profile was made (or changed) after
    #: the sheet was printed. The hover card then says so instead of the
    #: profiling card's "keep it for the profile" (Knut, #182 5983480953).
    profile_newer: bool = False

    @property
    def is_prediction(self) -> bool:
        return self.source == SOURCE_PREDICTION and bool(self.by_loc)

    def expected_for(self, loc: str) -> "tuple | None":
        if not self.is_prediction:
            return None
        return self.by_loc.get(str(loc))


def estimate(reason: str, *, profile_newer: bool = False) -> LiveExpected:
    """Today's rule: the chart's own expected colour, at the estimated limit."""
    return LiveExpected(SOURCE_ESTIMATE, reason, profile_newer=profile_newer)


# ---------------------------------------------------------------------------
# The ONE substitution, used live and by the repaint (UMM 10.6)
# ---------------------------------------------------------------------------

def apply_expected(patches: "Iterable[dict]",
                   expected: "LiveExpected | None") -> "list[dict]":
    """Patch events with the expected colour taken from *expected*.

    Each patch dict (``loc``, ``exyz``, ``xyz``, ``de``, ...) whose location
    has a prediction comes back as a COPY with ``exyz`` replaced and ``de``
    recomputed exactly as the engine computes it
    (:func:`~workflow.measurement_report.engine_patch_de`: ΔE*ab, CIE76, both
    sides against ArgyllCMS's D50 after dividing by 100). Every other patch,
    and everything when *expected* is not a prediction, comes back unchanged.
    The live strip, the live patch, the whole-chart read and the repaint from
    disk all go through here, so the outline after a measurement is the
    outline during it.
    """
    out: "list[dict]" = []
    pred = expected if (expected is not None and expected.is_prediction) else None
    from workflow.measurement_report import engine_patch_de
    for p in patches:
        if pred is None:
            out.append(p)
            continue
        exyz = pred.expected_for(str(p.get("loc", "")))
        if exyz is None:
            out.append(p)
            continue
        q = dict(p)
        q["exyz"] = [float(v) for v in exyz[:3]]
        q["de"] = round(float(engine_patch_de(q["exyz"], p.get("xyz", [0, 0, 0]))), 2)
        out.append(q)
    return out


# ---------------------------------------------------------------------------
# Deciding, and predicting
# ---------------------------------------------------------------------------

_CACHE: "dict[tuple, LiveExpected]" = {}
_CACHE_MAX = 16


def clear_cache() -> None:
    _CACHE.clear()


def _mtime_iso(path: Path) -> str:
    """A file's modification time as the print record writes it."""
    return datetime.fromtimestamp(Path(path).stat().st_mtime).isoformat(
        timespec="seconds")


def _parse_iso(text: str) -> "datetime | None":
    try:
        return datetime.fromisoformat(str(text).strip())
    except (TypeError, ValueError):
        return None


def build_light_problem(profile_settings: "Mapping | None") -> str:
    """Why the run's profile predicts colour under another light, or ''.

    Read from the run's Build Profile settings (``RunMeta.profile_settings``,
    Manual and Guided both): an illuminant other than D50 (``-i``), an
    observer other than 1931 2° (``-o``), or FWA compensation (``-f``).
    """
    s = dict(profile_settings or {})
    for k in _ILLUMINANT_KEYS:
        v = str(s.get(k) or "").strip()
        if v not in _DEFAULT_ILLUMINANTS:
            return f"the profile was built with illuminant {v} (-i)"
    for k in _OBSERVER_KEYS:
        v = str(s.get(k) or "").strip()
        if v not in _DEFAULT_OBSERVERS:
            return f"the profile was built with observer {v} (-o)"
    for k in _FWA_KEYS:
        if bool(s.get(k)):
            return "the profile was built with FWA compensation (-f)"
    return ""


def _rgb_rows(ti2: Path) -> "list[tuple[str, tuple[float, float, float]]]":
    """``[(loc, (r, g, b) on 0..100)]`` from the chart, in file order.

    Raises ``ValueError`` for a chart that is not RGB. Values on a 0..255
    scale are brought to 0..100, as the colour ranges do.
    """
    from workflow.printer_calibration import read_table
    fields, rows, _kw = read_table(ti2)
    if not all(f in fields for f in ("RGB_R", "RGB_G", "RGB_B")):
        raise ValueError("not an RGB chart")
    out = []
    vals = []
    for sid, row in rows.items():
        loc = str(row.get("SAMPLE_LOC", sid)).strip('"') or sid
        rgb = tuple(float(row[k]) for k in ("RGB_R", "RGB_G", "RGB_B"))
        out.append((loc, rgb))
        vals.extend(rgb)
    if vals and max(vals) > 100.5:
        out = [(loc, tuple(v * 100.0 / 255.0 for v in rgb)) for loc, rgb in out]
    return out


def _page_bits(ti2: Path) -> int:
    """8 or 16: the bit depth of the chart's page images, which is what
    cctiff converted at print time (8 when none can be read)."""
    try:
        from workflow.printer_calibration import _pages_for
        import tifffile
        for page in _pages_for(Path(ti2)):
            with tifffile.TiffFile(page) as t:
                return 16 if t.pages[0].dtype.itemsize >= 2 else 8
    except Exception:      # noqa: BLE001 — a guess, and the safe one
        log.debug("could not read the page bit depth of %s", ti2, exc_info=True)
    return 8


def convert_like_the_print(rgb100: "list[tuple[float, float, float]]",
                           profile: Path, *, intent: str, source_profile: str,
                           bin_dir: "str | Path", bits: int = 8,
                           calibration: "Path | None" = None,
                           runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                           ) -> "list[tuple[float, float, float]]":
    """The device values cctiff wrote for these patches at print time.

    The patches become one row of pixels at the page's bit depth (the page
    pixels were rounded the same way), and go through
    ``cctiff -p -f T -i <intent> <source> -i <intent> <profile> [<cal>]``,
    the arguments :func:`workflow.verification_print.convert_pages_through_profile`
    used. Returns 0..100 values. Raises ``RuntimeError`` when cctiff is
    missing, refuses, or does not finish.
    """
    import numpy as np
    import tifffile
    from core.proc_text import run_text
    from core.resource_path import argyll_binary
    from workflow.cctiff_apply import convert_args
    from workflow.verification_print import intent_letter
    exe = Path(bin_dir) / argyll_binary("cctiff")
    if runner is subprocess.run and not exe.exists():
        raise RuntimeError(f"cctiff not found in {bin_dir}")
    top = 65535 if bits == 16 else 255
    dtype = np.uint16 if bits == 16 else np.uint8
    px = np.array([[round(v * top / 100.0) for v in rgb] for rgb in rgb100],
                  dtype=float).clip(0, top).astype(dtype)[None, :, :]
    with tempfile.TemporaryDirectory(prefix="chromiq-verify-expected-") as tmp:
        src = Path(tmp) / "patches.tif"
        dst = Path(tmp) / "patches-sent.tif"
        tifffile.imwrite(src, px, photometric="rgb", metadata=None)
        cmd = [str(exe), *convert_args(Path(source_profile), Path(profile),
                                       src, dst, intent=intent_letter(intent),
                                       calibration=calibration)]
        log.debug("verification expected colours: %s", " ".join(cmd))
        try:
            r = run_text(cmd, runner=runner, capture_output=True,
                         timeout=_TIMEOUT_S)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"cctiff did not finish within {_TIMEOUT_S} seconds") from exc
        except OSError as exc:
            raise RuntimeError(f"cctiff could not be started: {exc}") from exc
        if r.returncode != 0 or not dst.is_file():
            text = ((r.stderr or "") + "\n" + (r.stdout or "")).strip()
            last = text.splitlines()[-1] if text else f"exit {r.returncode}"
            raise RuntimeError(f"cctiff refused the conversion: {last}")
        with tifffile.TiffFile(dst) as t:
            out = np.asarray(t.pages[0].asarray(), dtype=float).reshape(-1, 3)
    if len(out) != len(rgb100):
        raise RuntimeError(f"cctiff returned {len(out)} pixels for "
                           f"{len(rgb100)} patches")
    return [tuple(float(v) * 100.0 / top for v in row) for row in out]


def _record_calibration(rec: dict, run, verify_ti2: Path) -> "tuple[dict, bool]":
    """The record's ``printer_calibration``, or one worked out now for a
    record written before B7 (``(block, from_record)``)."""
    block = rec.get("printer_calibration")
    if isinstance(block, dict) and block:
        return dict(block), True
    from workflow import printer_calibration as pc
    try:
        prof = pc.run_calibration_mode(run) if run is not None else pc.MODE_UNKNOWN
        ver = pc.calibration_mode_of(verify_ti2)
    except Exception:      # noqa: BLE001
        prof, ver = pc.MODE_UNKNOWN, pc.MODE_UNKNOWN
    return {"profiling_chart": prof, "verification_chart": ver,
            "applied_at_print": None}, False


def _run_cal_sha1(run) -> str:
    from workflow import printer_calibration as pc
    try:
        return pc.cal_sha1_of_text(pc.embedded_cal_text(pc.run_cal_source(run)))
    except Exception:      # noqa: BLE001
        return ""


def _sent_values_plan(rec: dict, run, verify_ti2: Path,
                      ) -> "tuple[str, Path | None, str]":
    """``(kind, calibration, why)`` for what was sent. *kind* is ``raw``,
    ``through`` or ``''`` (cannot be known: fall back, *why* says so).
    *calibration* is the ``.cal`` source to append to the cctiff chain (a
    ``.ti3``/``.ti2`` carrying it), or None for "predict before the
    calibration" / no calibration."""
    from workflow import printer_calibration as pc
    from workflow.verification_print import COLOUR_RAW, COLOUR_THROUGH
    cal, from_record = _record_calibration(rec, run, verify_ti2)
    prof = str(cal.get("profiling_chart") or pc.MODE_UNKNOWN)
    ver = str(cal.get("verification_chart") or pc.MODE_UNKNOWN)
    applied = cal.get("applied_at_print")
    if rec.get("colour") == COLOUR_RAW:
        if ver == pc.MODE_OLD_ENGINE_APPLY:
            return "", None, ("the verification chart holds calibrated device "
                              "values (an older layout-engine -K chart)")
        if ver == pc.MODE_APPLY:
            if prof != pc.MODE_APPLY:
                return "", None, ("the sheet was printed with a calibration "
                                  "the profile was not built with")
            if pc.cal_sha1_of_text(pc.embedded_cal_text(verify_ti2)) != \
                    _run_cal_sha1(run):
                return "", None, ("the sheet was printed with another "
                                  "calibration than the profile was built with")
            return "raw", None, ("raw, with the calibration the profile was "
                                 "built with: predicted before the calibration")
        if prof == pc.MODE_APPLY:
            return "", None, ("the sheet was printed without the calibration "
                              "the profile was built with")
        return "raw", None, "raw: the chart's own RGB was sent"
    if rec.get("colour") == COLOUR_THROUGH:
        if ver in (pc.MODE_APPLY, pc.MODE_OLD_ENGINE_APPLY):
            return "", None, ("the verification chart itself was built with "
                              "the calibration applied")
        if prof == pc.MODE_APPLY:
            if not from_record or not applied:
                return "", None, ("it is not recorded that the run's "
                                  "calibration was applied at print time")
            rec_sha = str(cal.get("cal_sha1") or "")
            if rec_sha and rec_sha == _run_cal_sha1(run):
                return "through", None, (
                    "through the profile, then the calibration the profile "
                    "was built with: predicted before the calibration")
            src = Path(str(cal.get("cal_from") or ""))
            if (str(cal.get("cal_from") or "") and src.is_file() and rec_sha
                    and pc.cal_sha1_of_text(pc.embedded_cal_text(src)) == rec_sha):
                return "through", src, (
                    "through the profile and a calibration the profile was "
                    "not built with: predicted from the values sent")
            return "", None, ("the calibration applied at print time can no "
                              "longer be found")
        return "through", None, "through the profile: cctiff's values were sent"
    return "", None, "the print record does not say how the sheet was printed"


def live_expected(ti2: "str | Path", record_ti3: "str | Path", run, *,
                  bin_dir: "str | Path",
                  runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                  use_cache: bool = True) -> LiveExpected:
    """The expected colours for measuring the verification chart *ti2*.

    *record_ti3* is the measurement whose print record applies
    (:func:`workflow.verification_print.read_print_record` walks from it: a
    dated verification's own ``chart/`` snapshot first, then the live record
    beside the verification chart). *run* is the profiling run the
    verification belongs to. Never raises: every failure is the estimate, with
    the reason, and the reason is logged.
    """
    try:
        result = _decide(Path(ti2), Path(record_ti3), run, bin_dir=bin_dir,
                         runner=runner, use_cache=use_cache)
    except Exception as exc:      # noqa: BLE001 — a preview is never worth a crash
        log.warning("verification expected colours could not be worked out",
                    exc_info=True)
        result = estimate(f"the prediction failed: {exc}")
    if result.is_prediction:
        log.info("verification expected colours: the profile's prediction "
                 "(%s; %d patches, limit for a verification judged against its "
                 "profile, strip outlier test off) for %s", result.reason,
                 len(result.by_loc), Path(ti2).name)
    else:
        log.info("verification expected colours: the chart's sRGB estimate "
                 "(limit for a chart with estimated colours), because %s; %s",
                 result.reason, Path(ti2).name)
    return result


def report_prediction(ti2: "str | Path", record_ti3: "str | Path", run, *,
                      bin_dir: "str | Path", intent: str = "a",
                      runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                      ) -> LiveExpected:
    """The run profile's prediction of what was printed on a verification
    sheet, for the Measurement Report's PROFILE ACCURACY (Knut, #182
    6045500910, answer 1 to 6044584365): exactly the live check's decision
    and chain (:func:`live_expected`), with the forward table asked in
    *intent* (``"a"`` absolute, ``"r"`` relative, the print's own when the
    sheet is judged against its paper). Never raises; logs nothing."""
    try:
        return _decide(Path(ti2), Path(record_ti3), run, bin_dir=bin_dir,
                       runner=runner, use_cache=True, xyz_intent=intent)
    except Exception as exc:      # noqa: BLE001 — a report is never worth a crash
        return estimate(f"the prediction failed: {exc}")


def _decide(ti2: Path, record_ti3: Path, run, *, bin_dir, runner,
            use_cache: bool, xyz_intent: str = "a") -> LiveExpected:
    from workflow.verification_print import (COLOUR_RAW, COLOUR_THROUGH,
                                             ROUTE_CHROMIQ, read_print_record)
    if not ti2.is_file():
        return estimate("the verification chart is missing")
    rec = read_print_record(record_ti3)
    if not isinstance(rec, dict):
        return estimate("the sheet has no print record (printed outside "
                        "ChromIQ, or before ChromIQ recorded its prints)")
    if (rec.get("route") != ROUTE_CHROMIQ
            or not str(rec.get("printed_at") or "").strip()
            or rec.get("colour") not in (COLOUR_RAW, COLOUR_THROUGH)):
        return estimate("the sheet was not printed by ChromIQ")
    if run is None:
        return estimate("the verification belongs to no profiling run")
    try:
        profile = Path(run.built_profile_icc())
    except Exception:      # noqa: BLE001
        profile = None
    if profile is None or not profile.is_file():
        return estimate("the run has no profile")
    # THE PROFILE THE SHEET WAS PRINTED WITH, unchanged since (Knut's Q4).
    if rec.get("colour") == COLOUR_THROUGH:
        if str(rec.get("profile") or "") != profile.name:
            return estimate(f"the sheet was printed through "
                            f"{rec.get('profile') or 'another profile'}, and "
                            f"the run's profile is now {profile.name}")
        if str(rec.get("profile_mtime") or "") != _mtime_iso(profile):
            return estimate("the profile has changed since the sheet was "
                            "printed (its modification time differs)",
                            profile_newer=True)
    else:
        printed = _parse_iso(rec.get("printed_at"))
        built = _parse_iso(_mtime_iso(profile))
        if printed is None or built is None:
            # Not known to be newer: the card must not say "the profile was
            # made after this sheet was printed" (review of beta 11).
            return estimate("the print or the profile has no readable date, "
                            "so the profile cannot be shown to predate the "
                            "print")
        if built > printed:
            return estimate("the profile has changed since the sheet was "
                            "printed (it is newer than the print)",
                            profile_newer=True)
    try:
        settings = getattr(run.load_meta(), "profile_settings", None)
    except Exception:      # noqa: BLE001
        settings = None
    light = build_light_problem(settings)
    if light:
        return estimate(light)
    kind, cal_src, why = _sent_values_plan(rec, run, ti2)
    if not kind:
        return estimate(why)
    try:
        rows = _rgb_rows(ti2)
    except (OSError, ValueError) as exc:
        return estimate(f"the chart's RGB values could not be read ({exc})")
    if not rows:
        return estimate("the chart has no patches")

    st = ti2.stat()
    key = (str(ti2), st.st_mtime_ns, json.dumps(rec, sort_keys=True, default=str),
           str(profile), profile.stat().st_mtime_ns, str(bin_dir), kind,
           str(cal_src or ""), _sha1_of(cal_src), xyz_intent)
    if use_cache and runner is subprocess.run and key in _CACHE:
        return _CACHE[key]

    # Both tools run on the GUI thread (session start, repaint), so a wedged
    # Argyll must not freeze the window for long, and a failure is remembered
    # like a success so it is not retried on every repaint (review AQ2,
    # 2026-10-03). The fallback it gives is the same either way.
    result = _predict(ti2, rows, rec, profile, kind, cal_src, why, bin_dir=bin_dir,
                      runner=_capped(runner), xyz_intent=xyz_intent)
    if use_cache and runner is subprocess.run:
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.clear()
        _CACHE[key] = result
    return result


def _capped(runner):
    """*runner* with every ``timeout=`` capped at :data:`_GUI_TIMEOUT_S`."""
    def run(*args, **kw):
        t = kw.get("timeout")
        kw["timeout"] = _GUI_TIMEOUT_S if t is None else min(t, _GUI_TIMEOUT_S)
        return runner(*args, **kw)
    return run


def _predict(ti2, rows, rec, profile, kind, cal_src, why, *, bin_dir,
             runner, xyz_intent: str = "a") -> LiveExpected:
    from workflow.verification_print import recorded_source_profile
    rgb = [r for _loc, r in rows]
    if kind == "through":
        # the recorded source, else the same file here (beta-12 review: the
        # report's source reference follows the same rule)
        src = recorded_source_profile(rec.get("source_profile"), bin_dir)
        if not src:
            return estimate("the sRGB source profile of the conversion is missing")
        cal_file = None
        try:
            with tempfile.TemporaryDirectory(prefix="chromiq-verify-cal-") as tmp:
                if cal_src is not None:
                    from workflow.printer_calibration import extract_cal
                    cal_file = extract_cal(cal_src, Path(tmp) / "printed.cal")
                    if cal_file is None:
                        return estimate("the calibration applied at print "
                                        "time can no longer be read")
                sent = convert_like_the_print(
                    rgb, profile, intent=str(rec.get("intent") or "relative"),
                    source_profile=src, bin_dir=bin_dir, bits=_page_bits(ti2),
                    calibration=cal_file, runner=runner)
        except RuntimeError as exc:
            return estimate(str(exc))
    else:
        sent = rgb
    from workflow.xicclu_runner import XiccluError, forward_xyz
    try:
        xyz = forward_xyz(sent, profile, bin_dir, intent=xyz_intent,
                          runner=runner)
    except (XiccluError, OSError, subprocess.SubprocessError) as exc:
        return estimate(f"xicclu could not predict the patches ({exc})")
    if len(xyz) != len(rows):
        return estimate("xicclu returned a different number of patches")
    by_loc = {loc: tuple(float(v) for v in x[:3])
              for (loc, _rgb), x in zip(rows, xyz)}
    return LiveExpected(SOURCE_PREDICTION, f"{why}; profile {profile.name}",
                        by_loc, route=str(rec.get("colour")))


def _sha1_of(path: "Path | None") -> str:
    if path is None:
        return ""
    try:
        return hashlib.sha1(Path(path).read_bytes()).hexdigest()
    except OSError:
        return ""
