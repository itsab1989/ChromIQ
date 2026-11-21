"""The pace of a hand dual strip (after 4.3.54, 2026-11-21).

The helper's ``dual_pass_result`` for a hand strip carries, from helper
2026-11-21b (``"pace": true``), what a person needs to learn the pace and
what a tester's app log must hold to tell why a pass was refused:

* ``lamp_s`` / ``uv_s``: each pass's time, its readings x their integration
  time (the instrument reads back to back while the button is held), and
  ``reading_ms``; ``lamp_readings`` and ``uv_readings``;
* ``lamp_travel`` / ``uv_travel`` (ruler COUNTS, first to last reading) and
  ``lamp_dir`` / ``uv_dir`` (+1 up the ruler, -1 down). The ruler's mm scale
  is not measured for the i1Pro 2, so no speed in mm/s is ever stated;
* ``lamp_cells``: ArgyllCMS's readings per patch in the lamp pass (its
  trimmed cells), ``uv_counts``: the UV readings per patch (the cut);
  ``fewest_per_patch``, ``need`` (3), ``edge_steps`` (0.5);
* ``lamp_off_ms``, ``uv_dark_ms``, ``uv_trigger_ms``, ``uv_done_ms``: when the
  lamp went out, the dark reading before the UV pass, the UV pass's trigger
  and its end, in ms after the lamp pass's readings were in (-1 unknown);
* ``flatness`` / ``window_flatness``: the alignment gates' measures over the
  central 60 % and over the averaging window (-1 not judged), and
  ``max_window_flatness`` (fix round of 2026-11-21, review B1).

An older helper sends none of this; then nothing here says anything and the
texts are those of 4.3.54. Texts: §M-PROPOSED M-DUAL-PASS-PACE, -PACE-CLOSE,
-TOO-FAST; docs/design/i1pro2_dual_scan.md section 17.
"""
from __future__ import annotations

import logging
import math
import statistics

from core.i18n import decimal_text

log = logging.getLogger(__name__)

GOOD = "#5cb85c"     # the reading-speed panel's own colours (tab_measure)
CLOSE = "#e0a63a"
TOO_FAST = "#ff6b6b"


def _num(v) -> "float | None":
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def has_pace(ev: dict) -> bool:
    """The event carries the pace (a helper from 2026-11-21b, a hand strip
    that got as far as the cut)."""
    ev = ev or {}
    return bool(ev.get("pace")) and _num(ev.get("uv_s")) is not None and \
        _num(ev.get("lamp_s")) is not None and _num(ev.get("need")) is not None


def _counts(ev: dict, key: str) -> "list[int]":
    out = []
    for v in (ev or {}).get(key) or []:
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            pass
    return out


def fewest(ev: dict) -> "int | None":
    c = _counts(ev, "uv_counts")
    if c:
        return min(c)
    try:
        f = int((ev or {}).get("fewest_per_patch"))
    except (TypeError, ValueError):
        return None
    return f if f >= 0 else None


#: the longest UV pass the helper takes (CQ_DUAL_MAX_UV_READINGS readings)
MAX_UV_READINGS = 4000
#: a time is named only while it stays this far under that limit: a slower
#: pass is seldom exactly as slow as planned (review M3)
CAP_SHARE = 0.8
#: green from need + 2 readings on the emptiest patch: at need + 1 a pass
#: about a quarter faster is already refused (review m4)
ROOM = 2


def target_seconds(uv_s: float, fewest_: int, need: int) -> float:
    """How long the refused pass should take: slower by (need + 0.5) / fewest,
    so the emptiest patch expects half a reading MORE than the limit (a count
    of readings scatters by about a reading; aiming at the limit itself
    passes only about half the time, review m1), rounded UP to half a
    second."""
    if fewest_ <= 0:
        return uv_s
    t = uv_s * (need + 0.5) / fewest_
    return math.ceil(t * 2.0 - 1e-9) / 2.0


def cap_seconds(ev: dict) -> "float | None":
    """The longest UV pass, in seconds of reading, the helper takes."""
    rms = _num((ev or {}).get("reading_ms"))
    return MAX_UV_READINGS * rms / 1000.0 if rms and rms > 0 else None


def reading_seconds(ev: dict) -> "float | None":
    """The second pass's seconds of reading (the number the texts state),
    for the time under the strip: one number for one pass (review m3)."""
    return _num((ev or {}).get("uv_s")) if has_pace(ev) else None


def accepted_text(ev: dict, strip_name: str) -> "tuple[str, str, str] | None":
    """(title, body, colour) for an accepted strip with the pace, else None."""
    from workflow import measurement_messages as M
    if not has_pace(ev):
        return None
    f, need = fewest(ev), int(_num(ev.get("need")))
    if f is None or f < need:
        return None
    msg, colour = ((M.M_DUAL_PASS_PACE_CLOSE, CLOSE) if f < need + ROOM
                   else (M.M_DUAL_PASS_PACE, GOOD))
    title, body = msg.render(strip=strip_name, fewest=f, need=need,
                             lamp_s=decimal_text(_num(ev["lamp_s"]), 1),
                             uv_s=decimal_text(_num(ev["uv_s"]), 1))
    return title, body, colour


def too_fast_case(ev: dict) -> "str | None":
    """Which advice a too-fast refusal gets: "uneven" (the pass was slow
    enough as a whole: half of the patches got twice what is needed), "time"
    (a time is named), "even" (the time would come near the pass's limit:
    none is named), or None (no numbers: 4.3.54's sentence)."""
    if str((ev or {}).get("why") or "") != "uv_pass_too_fast" or not has_pace(ev):
        return None
    f, need, uv_s = fewest(ev), int(_num(ev.get("need"))), _num(ev.get("uv_s"))
    if f is None or f <= 0 or f >= need or not uv_s or uv_s <= 0:
        return None
    counts = _counts(ev, "uv_counts")
    if counts and statistics.median(counts) >= 2 * need:
        return "uneven"
    cap = cap_seconds(ev)
    if cap is None or target_seconds(uv_s, f, need) >= CAP_SHARE * cap:
        return "even"
    return "time"


def too_fast_text(ev: dict) -> "tuple[str, str] | None":
    """(title, body) for a second pass refused as too fast, with its numbers;
    None when the event does not say them (4.3.54's sentence is used)."""
    from workflow import measurement_messages as M
    case = too_fast_case(ev)
    if case is None:
        return None
    f, need, uv_s = fewest(ev), int(_num(ev.get("need"))), _num(ev.get("uv_s"))
    if case == "uneven":
        med = statistics.median(_counts(ev, "uv_counts"))
        return M.M_DUAL_PASS_TOO_FAST_UNEVEN.render(
            fewest=f, need=need, median=int(med))
    if case == "even":
        cap = cap_seconds(ev) or 19.5
        return M.M_DUAL_PASS_TOO_FAST_EVEN.render(
            fewest=f, need=need, cap_s=decimal_text(math.floor(cap), 0))
    return M.M_DUAL_PASS_TOO_FAST.render(
        fewest=f, need=need, uv_s=decimal_text(uv_s, 1),
        target_s=decimal_text(target_seconds(uv_s, f, need), 1))


def too_fast_line(ev: dict) -> "tuple[str, str] | None":
    """The short reading-speed line after a too-fast refusal (review m2)."""
    from workflow import measurement_messages as M
    if too_fast_case(ev) is None:
        return None
    return M.M_DUAL_PASS_TOO_FAST_LINE.render(
        fewest=fewest(ev), need=int(_num(ev.get("need"))),
        uv_s=decimal_text(_num(ev.get("uv_s")), 1))


def refusal_text(ev: dict) -> "tuple[str, str] | None":
    """The window's reason for a refused second pass with a text of its own
    after 4.3.54: too fast with its numbers, or not lined up (B1)."""
    from workflow import measurement_messages as M
    if str((ev or {}).get("why") or "") == "uv_pass_shifted":
        return M.M_DUAL_PASS_SHIFTED.render()
    return too_fast_text(ev)


def log_result(ev: dict) -> None:
    """The app log: one line per dual pass verdict with the pace (INFO), the
    per-patch lists in full (DEBUG). No serial, no path: numbers and ids."""
    try:
        from core.app_log import line
        ev = ev or {}
        kv = {"strip": str(ev.get("strip") or "") or "-",
              "what": str(ev.get("what") or "strip"),
              "ok": bool(ev.get("ok")), "why": str(ev.get("why") or "") or "-",
              "uv_readings": ev.get("uv_readings"),
              "fewest": ev.get("fewest_per_patch"),
              "pairing": str(ev.get("pairing") or "") or "-"}
        if has_pace(ev):
            lc, uc = _counts(ev, "lamp_cells"), _counts(ev, "uv_counts")
            kv.update({
                "need": ev.get("need"), "edge_steps": _num(ev.get("edge_steps")),
                "reading_ms": _num(ev.get("reading_ms")),
                "lamp_dir": ev.get("lamp_dir"), "lamp_travel": ev.get("lamp_travel"),
                "lamp_readings": ev.get("lamp_readings"), "lamp_s": _num(ev.get("lamp_s")),
                "uv_dir": ev.get("uv_dir"), "uv_travel": ev.get("uv_travel"),
                "uv_s": _num(ev.get("uv_s")),
                "lamp_cell_min": min(lc) if lc else None,
                "lamp_cell_median": statistics.median(lc) if lc else None,
                "uv_count_min": min(uc) if uc else None,
                "uv_count_median": statistics.median(uc) if uc else None,
                "lamp_off_ms": ev.get("lamp_off_ms"), "uv_dark_ms": ev.get("uv_dark_ms"),
                "uv_trigger_ms": ev.get("uv_trigger_ms"),
                "uv_done_ms": ev.get("uv_done_ms"),
                # the two alignment measures (-1: not judged) and the window's limit
                "flatness": _num(ev.get("flatness")),
                "window_flatness": _num(ev.get("window_flatness")),
                "max_window_flatness": _num(ev.get("max_window_flatness")),
                # second fix round: the UV pass lined up (offset subtracted, how clearly)
                "align": str(ev.get("align") or "") or None,
                "offset_steps": _num(ev.get("offset_steps")),
                "offset_rise": _num(ev.get("offset_rise"))})
            if str(ev.get("why") or "") == "uv_pass_too_fast":
                f, need, uv_s = fewest(ev), _num(ev.get("need")), _num(ev.get("uv_s"))
                if f and need and uv_s:
                    kv["advice"] = too_fast_case(ev) or "-"
                    kv["slower_factor"] = round((need + 0.5) / f, 2)
                    kv["target_s"] = target_seconds(uv_s, f, int(need))
                    kv["cap_s"] = cap_seconds(ev)
            line("dual pass", **kv)
            line("dual pass patches", _level=logging.DEBUG, strip=kv["strip"],
                 lamp_cells=",".join(str(v) for v in lc) or "-",
                 uv_counts=",".join(str(v) for v in uc) or "-")
        else:
            line("dual pass", **kv)
    except Exception:      # noqa: BLE001 - a log line never stops a read
        log.debug("dual pass log line", exc_info=True)
