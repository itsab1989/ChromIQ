"""(3a) The Measure tab's judging, without a window: what each patch's
outline is after every strip (or patch) of a measurement.

This mirrors, step for step, what ``ui/tabs/tab_measure.py`` on
``fix/4.3.3-beta11-neighbours`` does with an engine strip
(``_on_strip_measured``) and a patch by patch reading
(``_on_patch_measured``); the on-screen driver checks the same cases in the
real tab:

1. the strip's readings go into the neighbour check first, which judges
   again (``_neighbour_feed``);
2. each patch: ΔE76 against its expected colour, the red rule's *warn* (past
   the limit, 95 for an estimated chart, AND past its strip's Tukey fence;
   patch by patch the limit alone), OR the neighbour check's suspicion, into
   ``FlagJudge.judge`` with its stand-out from the strip's median and its
   strip (``_judge_with_neighbours``);
3. patches of earlier strips whose neighbour verdict the strip changed are
   judged again, not live (``_neighbour_rejudge``);
4. ``FlagJudge.rejudge`` (``_apply_flag_rejudge``).

"Was a strip read twice?" (``MeasureManager._check_read_twice``) runs on
every engine strip with the strips measured so far; when it asks, the user
answers "Re-read" if the strip really carries another strip's colours
(the ground truth), else "Keep", as a careful user would.

FlagJudge comes from THIS tree (``workflow/patch_flags.py``, unchanged on
the neighbours branch); the neighbour check from the branch, copied
(:func:`common.neighbour_module`).
"""
from __future__ import annotations

import statistics

from tests.neighbour_campaign.common import de76, neighbour_module, xyz_to_lab
from workflow import patch_flags as PF
from workflow.icc_info import xyz_to_lab as icc_xyz_to_lab
from workflow.strip_read_twice import looks_read_twice
from workflow.strip_read_twice import xyz_to_lab as srt_lab


def strip_outlier_fence(des) -> float:
    """``tab_measure._strip_outlier_fence`` (Q3 + 1.5 IQR, 0 under 4)."""
    if len(des) < 4:
        return 0.0
    s = sorted(des)

    def pct(p):
        k = (len(s) - 1) * p
        f = int(k)
        c = min(f + 1, len(s) - 1)
        return s[f] + (s[c] - s[f]) * (k - f)
    q1, q3 = pct(0.25), pct(0.75)
    return q3 + 1.5 * (q3 - q1)


def outline(v) -> str:
    """What the preview draws for a verdict."""
    if v is None:
        return ""
    f = v.flag
    if f is True:
        return "red"
    if f == PF.FLAG_CONFIRMED:
        return "yellow" if v.prev_de is not None else "yellow_peer"
    if f == PF.FLAG_LEARNED:
        return "yellow_learned"
    return ""


class TabEmulator:
    def __init__(self, chart, *, limit: float = PF.ESTIMATED_DEFAULT_DE,
                 buffer: float = 10.0, fence: bool = True,
                 neighbour_applies: bool = True, nb_mod=None):
        self.chart = chart
        self.limit = float(limit)
        self.fence_on = bool(fence)
        self.applies = bool(neighbour_applies)
        mod = nb_mod or neighbour_module()[0]
        self.nc = mod.NeighbourCheck(buffer=buffer)
        self.judge = PF.FlagJudge(white=PF.chart_white(chart.ti2),
                                  device_ranges=PF.chart_device_ranges(chart.ti2))
        self.inputs: dict = {}            # loc -> (exp_lab, meas_lab, de, warn, standout)
        self.by_limit: set = set()        # locs red by the limit rule at least once
        self.measured: dict = {}          # strip -> labs (read-twice memory)
        self.suspect_strips: dict = {}
        self.design = {}
        idx = chart.strip_members()
        for s, m in idx.items():
            self.design[s] = [tuple(chart.rgb[i]) for i in m]
        self.read_twice_log: list = []

    # ---- one batch -------------------------------------------------------------
    def read_strip(self, label: str, xyz_by_loc: dict, *, engine=True):
        """An engine strip *label* with readings ``{loc: xyz}``; returns the
        read-twice finding (or None)."""
        c = self.chart
        m = c.strip_members()[label]
        locs = [c.locs[i] for i in m if c.locs[i] in xyz_by_loc]
        found = None
        if engine:
            labs = [srt_lab(xyz_by_loc[loc]) for loc in locs]
            trusted = {k: v for k, v in self.measured.items()
                       if k not in self.suspect_strips}
            found = looks_read_twice(label, labs, trusted, self.design.get)
            self.measured[label] = labs
            self.suspect_strips.pop(label, None)
            if found is not None:
                self.suspect_strips[label] = found.like
        self._batch(locs, xyz_by_loc, strip_mode=True)
        return found

    def read_patch(self, loc: str, xyz) -> None:
        self._batch([loc], {loc: xyz}, strip_mode=False)

    def _batch(self, locs, xyz_by_loc, *, strip_mode):
        c = self.chart
        ix = c.index()
        exyz = {loc: c.exp_xyz[ix[loc]] for loc in locs}
        changed = {}
        if self.applies:
            for loc in locs:
                self.nc.set_reading(loc, exyz[loc], xyz_by_loc[loc],
                                    c.strips[ix[loc]])
            changed = self.nc.evaluate()
        des = [de76(xyz_to_lab(exyz[l]), xyz_to_lab(xyz_by_loc[l])) for l in locs]
        fence = strip_outlier_fence(des) if (strip_mode and self.fence_on) else 0.0
        median = statistics.median(des) if des else 0.0
        for loc, de in zip(locs, des):
            warn = de >= self.limit and de >= fence
            if warn:
                self.by_limit.add(loc)
            exp_lab = icc_xyz_to_lab(tuple(v / 100.0 for v in exyz[loc]))
            meas_lab = icc_xyz_to_lab(tuple(v / 100.0 for v in xyz_by_loc[loc]))
            standout = de - median if strip_mode else None
            self.inputs[loc] = (exp_lab, meas_lab, de, warn, standout)
            f = self.nc.finding(loc) if self.applies else None
            sus = bool(f is not None and f.suspect)
            self.judge.judge(loc, exp_lab, meas_lab, de, warn or sus,
                             standout=standout, live=True, strip=c.strips[ix[loc]])
        done = set(locs)
        for loc, f in changed.items():
            if loc in done or loc not in self.inputs:
                continue
            exp_lab, meas_lab, de, warn, standout = self.inputs[loc]
            self.judge.judge(loc, exp_lab, meas_lab, de, warn or f.suspect,
                             standout=standout, live=False,
                             strip=c.strips[ix[loc]])
        self.judge.rejudge()

    # ---- what is on screen -----------------------------------------------------
    def outlines(self) -> dict:
        """``{loc: "red" | "yellow" | "yellow_peer" | "yellow_learned"}``."""
        out = {}
        for loc, v in self.judge._verdicts.items():
            o = outline(v)
            if o:
                out[loc] = o
        return out

    def suspects(self) -> list:
        return self.nc.suspects() if self.applies else []

    def summary_facts(self):
        """``tab_measure.neighbour_summary_facts``."""
        if not self.applies or len(self.nc) == 0:
            return None
        red, kept = [], []
        for loc in self.nc.suspects():
            v = self.judge._verdicts.get(loc)
            flag = getattr(v, "flag", PF.FLAG_RED)
            if flag is PF.FLAG_RED or flag is True:
                red.append(loc)
            elif flag == PF.FLAG_CONFIRMED and getattr(v, "prev_de", None) is not None:
                kept.append(loc)
        return {"red": PF.sorted_locs(red), "kept": PF.sorted_locs(kept),
                "checked": self.nc.checked_count(), "total": len(self.nc)}
