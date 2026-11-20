# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""The measurement's lines in the app log (4.3.50, A2, A3, A7, A8).

One line at each measurement START with what is in effect, one line per strip
as it is decided, the dual scan's / M0-M1-M2 start and end, and where each file
was written. The shapes (``core.app_log``)::

    measure start: reader=engine helper_build=... instrument_port=1 chart=T.ti2 patches=702 ...
    measure instrument: model=i1pro2 filter=...
    strip: id=A attempt=1 result=kept worst_de=1.2 engine_net=ok slip=ok read_twice=ok ...
    strip: id=? attempt=2 result=refused reason=misread ...
    conditions start: ... / conditions end: strips_all_three=N m0_only=[...] files=[...]
    file written: what=measurement path=~/ChromIQ/T/runs/run1/T.ti3

Everything here is called from the manager's existing handlers, AFTER the
event was handled, on the thread that handled it; nothing is sent, nothing
waits, nothing raises.
"""
from __future__ import annotations

import json
from pathlib import Path

from core.app_log import Clock, line, merged, never_raises

#: which ti2 keywords the start line reads (the header ends at BEGIN_DATA)
_TI2_KEYS = ("TARGET_INSTRUMENT", "STEPS_IN_PASS", "PASSES_IN_STRIPS2", "NUMBER_OF_SETS",
             "PAPER_SIZE", "ORIGINATOR")


@never_raises
def chart_summary(ti2_path) -> dict:
    """Pages, strips, patches per strip, patch size from a chart's .ti2 header and
    its ``.channels.json`` side file. Reads only the header lines. Never raises."""
    out: dict = {}
    try:
        p = Path(ti2_path)
        out["chart"] = p.name
        if p.is_file():
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                for n, raw in enumerate(fh):
                    if raw.strip() == "BEGIN_DATA" or n > 400:
                        break
                    parts = raw.strip().split(None, 1)
                    if len(parts) == 2 and parts[0] in _TI2_KEYS:
                        out[parts[0]] = parts[1].strip().strip('"')
        res = {"chart": out.get("chart"), "chart_instrument": out.get("TARGET_INSTRUMENT")}
        try:
            res["patches"] = int(out.get("NUMBER_OF_SETS", "") or 0) or None
        except ValueError:
            res["patches"] = None
        passes = [x for x in str(out.get("PASSES_IN_STRIPS2", "")).split(",") if x.strip()]
        if passes:
            try:
                res["pages"] = len(passes)
                res["strips"] = sum(int(x) for x in passes)
            except ValueError:
                pass
        res["patches_per_strip"] = out.get("STEPS_IN_PASS")
        res["layout"] = ("chromiq" if "ChromIQ" in str(out.get("ORIGINATOR", ""))
                         else "printtarg" if out.get("ORIGINATOR") else None)
        side = p.with_suffix(".channels.json")
        if side.is_file() and side.stat().st_size < 4_000_000:
            lay = (json.loads(side.read_text(encoding="utf-8")) or {}).get("layout") or {}
            dpi = float(lay.get("dpi") or 0)
            pt = (lay.get("patches") or [None])[0]
            if dpi > 0 and isinstance(pt, dict) and pt.get("w") and pt.get("h"):
                res["patch_mm"] = (f"{float(pt['w']) / dpi * 25.4:.1f}x"
                                   f"{float(pt['h']) / dpi * 25.4:.1f}")
        return res
    except Exception:      # noqa: BLE001
        return out or {"chart": str(ti2_path)}


def run_kind(ti1_path) -> str:
    """profile / verification / calibration, from the run's folder."""
    try:
        parts = Path(ti1_path).parts
        if "verifications" in parts:
            return "verification"
        if "cal" in parts:
            return "calibration"
        return "profile"
    except Exception:      # noqa: BLE001
        return "?"


@never_raises
def log_start(params, *, reader: str, helper_build: str = "", ruler: bool = False,
              dual: str = "off", lights: bool = False, conditions: str = "off") -> None:
    """The one line at a measurement's start. Never raises."""
    try:
        from workflow.measurement_condition import filter_code_from_args
        ti1 = Path(params.ti1_path)
        ti2 = ti1 if ti1.suffix.lower() == ".ti2" else ti1.with_suffix(".ti2")
        cs = chart_summary(ti2)
        mode = "patch_by_patch" if params.patch_by_patch else "strips"
        if getattr(params, "engine_xy_chart", False):
            mode += "+xy_tables"
        if getattr(params, "external_values", False):
            mode += "+external_values"
        from workflow.ti3_provenance import short_build
        line("measure start", reader=reader, helper_build=short_build(helper_build) or "-",
             instrument_port=params.instrument, chart=cs.get("chart"),
             chart_instrument=cs.get("chart_instrument"), patches=cs.get("patches"),
             pages=cs.get("pages"), strips=cs.get("strips"),
             patches_per_strip=cs.get("patches_per_strip"),
             patch_mm=cs.get("patch_mm"), layout=cs.get("layout"), mode=mode,
             filter=filter_code_from_args(params.extra_args) or "default",
             dual_scan=dual, conditions=conditions, ruler=ruler,
             margin_tolerance=bool(getattr(params, "engine_margin_tolerance", False)) and ruler,
             misaligned_check=bool(getattr(params, "engine_safenet", False)),
             lights=lights, high_res=bool(params.high_res), resume=bool(params.resume),
             run_kind=run_kind(ti1), page_pause=bool(getattr(params, "page_pause", False)),
             replay=getattr(params, "engine_replay", None) is not None,
             run_dir=str(ti1.parent))
    except Exception:      # noqa: BLE001
        pass


class StripLog:
    """Attempts and timing per strip, and the one line per strip decision."""

    def __init__(self) -> None:
        self.attempts: "dict[str, int]" = {}
        self.clock: "Clock | None" = None
        self.dual: "dict[str, dict]" = {}
        self.lines = 0

    @never_raises
    def ready(self) -> None:
        self.clock = Clock()

    def _took(self):
        return self.clock.s() if self.clock is not None else None

    @never_raises
    def decided(self, strip: str, result: str, /, **checks) -> None:
        try:
            s = str(strip or "?").strip() or "?"
            self.attempts[s] = self.attempts.get(s, 0) + 1
            if s in self.dual:
                checks.setdefault("dual_pass", self.dual.pop(s))
            from core.app_log import flat
            rest = {k: v for k, v in flat(checks, depth=2).items() if v is not None}
            rest = merged(rest, {"took_s": self._took()})
            line("strip", **merged({"id": s, "attempt": self.attempts[s],
                                    "result": result}, rest))
            self.lines += 1
            self.clock = None
        except Exception:      # noqa: BLE001
            pass


@never_raises
def written(what: str, path, /, **kv) -> None:
    """A8: where a file was written (the filter shortens the path)."""
    line("file written", **merged({"what": what, "path": str(path)}, kv))


#: S2: how often the end-of-measurement summary tries to read a file that is
#: being moved, and how long it waits in between
_READ_TRIES = 4
_READ_RETRY_S = 0.25


@never_raises
def log_measurement_end(main_ti3, *, code, conditions: bool, dual: bool,
                        strips_logged: int = 0, in_thread: bool = True) -> None:
    """A7 + A8: at a measurement's end, where its files are and, with the M0/M1/M2
    Beta or the dual scan, how many strips have all three conditions and which
    have M0 only. The files are read on a background thread (the GUI thread
    did no such reading before). Never raises."""
    def work():
        # S2 (4.3.50): every file is read FIRST, the lines written after. On
        # Windows a file being moved or replaced at this moment refuses to
        # open (a sharing violation): the reads are tried again briefly, and
        # no line is written twice.
        import time as _time
        for attempt in range(_READ_TRIES):
            try:
                out = _facts()
                break
            except OSError:
                if attempt == _READ_TRIES - 1:
                    line("measure end", exit=code, strips_logged=strips_logged,
                         files="not_readable")
                    return
                _time.sleep(_READ_RETRY_S)
        for fn, args, kw in out or []:
            fn(*args, **kw)

    def _facts() -> list:
        """The lines to write, as (function, args, kwargs). Raises OSError
        when a file could not be read; nothing is written then."""
        out: list = []
        try:
            main = Path(main_ti3)
            exists = main.is_file()
            out.append((line, ("measure end",), dict(
                exit=code, strips_logged=strips_logged,
                measurement=str(main) if exists else None,
                measurement_bytes=main.stat().st_size if exists else None)))
            if exists:
                out.append((written, ("measurement", main), {}))
            if not (conditions or dual) or not exists:
                return out
            from workflow import i1pro3_conditions as C
            files, partial = {}, []
            for cond in ("M0", "M1", "M2"):
                f = C.condition_file(main, cond)
                if f is None:
                    pf = C.partial_sibling_path(main, cond)
                    if pf is not None and Path(pf).is_file():
                        f = pf
                        partial.append(cond)
                files[cond] = f
                if f is not None and f != main:
                    out.append((written, (f"condition {cond}" + (
                        " (partial record)" if cond in partial else ""), f), {}))
            all_strips = C.strips_of(C._locs_of(main))
            m0_only = C.strips_of(C.m0_only_locs(main))
            three = files.get("M1") is not None and files.get("M2") is not None
            out.append((line, ("conditions end",), dict(
                main_condition=C.file_condition(main) or None,
                files=",".join(c for c, f in files.items() if f is not None) or None,
                partial=",".join(partial) or None,
                strips=len(all_strips),
                strips_all_three=(len(all_strips) - len(m0_only)) if three else 0,
                m0_only=" ".join(m0_only) if m0_only else None,
                dual_scan=dual)))
            if dual:
                try:
                    from core.file_manager import Run
                    rec = Run.for_dir(main.parent).dual_pass_record(main)
                    if rec is not None and Path(rec).is_file():
                        out.append((written, ("dual pass record", rec), {}))
                except OSError:
                    raise
                except Exception:      # noqa: BLE001
                    pass
        except OSError:
            raise
        except Exception:      # noqa: BLE001
            pass
        return out
    try:
        if in_thread:
            import threading
            threading.Thread(target=work, name="chromiq-measure-end-log",
                             daemon=True).start()
        else:
            work()
    except Exception:      # noqa: BLE001
        pass
