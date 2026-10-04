"""(3a) The Measure tab's judging, without a window: what each patch's
outline is after every strip (or patch) of a measurement.

This mirrors, step for step, what ``ui/tabs/tab_measure.py`` of THIS tree
(fix/4.3.3-beta3 at 6e9de104 or later: the reviewed beta-11 neighbour check)
does with an engine strip (``_on_strip_measured``) and a patch by patch
reading (``_on_patch_measured``); the on-screen driver checks the same cases
in the real tab:

1. the strip's readings go into the neighbour check first, which judges
   again (``_neighbour_feed`` -> ``_neighbour_redraw_set``: every patch whose
   verdict changed, and every suspect whose comparisons or figures changed);
2. each patch: ΔE76 against its expected colour, the red rule's *warn* (past
   the limit AND past its strip's Tukey fence; patch by patch, or on a
   verification judged against its profile, the limit alone), OR the
   neighbour check's suspicion, into ``FlagJudge.judge`` with its stand-out
   from the strip's median, its strip, and ``reread_only`` when the
   neighbour check suspects it (Knut 5984174575: only its own re-read can
   turn it yellow) (``_judge_with_neighbours``);
3. patches of earlier strips whose neighbour verdict (or card) the strip
   changed are judged again, not live (``_neighbour_rejudge``);
4. ``FlagJudge.rejudge`` (``_apply_flag_rejudge``).

"Was a strip read twice?" (``MeasureManager._check_read_twice``) runs on
every engine strip with the strips measured so far; when it asks, the user
answers "Re-read" if the strip really carries another strip's colours (the
ground truth), else "Keep", as a careful user would. "Re-read" sets the
strip's readings aside, and the neighbour check forgets them at once
(``_neighbour_forget``, review of beta 11).

The three kinds of chart (``kind``):

* ``"estimated"``: a profiling chart with ArgyllCMS's estimate, limit 95,
  strip fence on, neighbour check on;
* ``"accurate"``: a chart made with a pre-conditioning profile (targen -c,
  ACCURATE_EXPECTED_VALUES), limit 20, strip fence on, neighbour check on
  (Knut 5984174575);
* ``"verification"``: judged against its run profile's prediction, limit 10,
  NO strip fence, NO neighbour check, and NO misread summary in the closing
  window.

Everything is the product code of this tree: ``workflow/neighbour_check.py``,
``workflow/patch_flags.py``, ``workflow/strip_read_twice.py`` and the
summary's words from ``workflow/measurement_messages.py``.
"""
from __future__ import annotations

import statistics

from tests.neighbour_campaign.common import de76, neighbour_module, xyz_to_lab
from workflow import patch_flags as PF
from workflow.icc_info import xyz_to_lab as icc_xyz_to_lab
from workflow.strip_read_twice import looks_read_twice
from workflow.strip_read_twice import xyz_to_lab as srt_lab

#: The limit per chart kind (``patch_flags.warn_limit`` defaults).
LIMITS = {"estimated": PF.ESTIMATED_DEFAULT_DE,
          "accurate": PF.ACCURATE_DEFAULT_DE,
          "verification": PF.PREDICTION_DEFAULT_DE}


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
    if PF.is_corrected(f):
        return "green"
    if f == PF.FLAG_CONFIRMED:
        return "yellow" if v.prev_de is not None else "yellow_peer"
    if f == PF.FLAG_LEARNED:
        return "yellow_learned"
    return ""


def flag_outline(flag) -> str:
    """:func:`outline` for a bare flag (what the preview holds)."""
    if flag is True:
        return "red"
    if PF.is_corrected(flag):
        return "green"
    if PF.is_yellow(flag):
        return "yellow"
    return ""


class TabEmulator:
    def __init__(self, chart, *, kind: str = "estimated",
                 limit: "float | None" = None, buffer: float = 10.0,
                 fence: "bool | None" = None,
                 neighbour_applies: "bool | None" = None, nb_mod=None,
                 expected_xyz=None):
        self.chart = chart
        self.kind = kind
        self.limit = float(LIMITS[kind] if limit is None else limit)
        # The strip fence never applies to a verification judged against its
        # profile's prediction (_use_outlier_fence).
        self.fence_on = (kind != "verification") if fence is None else bool(fence)
        self.applies = ((kind != "verification") if neighbour_applies is None
                        else bool(neighbour_applies))
        mod = nb_mod or neighbour_module()[0]
        self.nc = mod.NeighbourCheck(buffer=buffer)
        self.judge = PF.FlagJudge(white=PF.chart_white(chart.ti2),
                                  device_ranges=PF.chart_device_ranges(chart.ti2))
        #: The expected colours judged against (a verification: the profile's
        #: prediction; else the chart's own .ti2).
        self.exp_xyz = chart.exp_xyz if expected_xyz is None else expected_xyz
        self.inputs: dict = {}            # loc -> (exp_lab, meas_lab, de, warn, standout)
        #: loc -> the reasons of its LAST live judgement:
        #: {"limit": bool, "neighbour": bool, "fence_hid": bool}
        self.why: dict = {}
        self.by_limit: set = set()        # locs red by the limit rule at least once
        self.by_neighbour: set = set()    # locs suspected by the neighbour check at least once
        self.fence_hid: set = set()       # past the limit, but hidden by the strip fence
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

    def set_aside(self, label: str) -> None:
        """The answer "Re-read" (or "it was the other strip"): the strip's
        readings are set aside, and the neighbour check forgets them now
        (``answer_read_twice`` + ``_neighbour_forget``)."""
        c = self.chart
        locs = [c.locs[i] for i in c.strip_members()[label]]
        if not self.applies:
            return
        for loc in locs:
            self.nc.forget(loc)
        self._rejudge_changed(self._redraw_set(), set())
        self.judge.rejudge()

    def keep(self, label: str) -> None:
        """The answer "Keep": the reading stays, and is trusted again."""
        self.suspect_strips.pop(label, None)

    def read_patch(self, loc: str, xyz) -> None:
        self._batch([loc], {loc: xyz}, strip_mode=False)

    def _redraw_set(self) -> dict:
        """``TabMeasure._neighbour_redraw_set``."""
        changed = self.nc.evaluate()
        for loc, f in self.nc.updated().items():
            if f.suspect:
                changed.setdefault(loc, f)
        return changed

    def _rejudge_changed(self, changed: dict, done) -> None:
        """``TabMeasure._neighbour_rejudge``."""
        c = self.chart
        ix = c.index()
        for loc, f in changed.items():
            if loc in done or loc not in self.inputs:
                continue
            exp_lab, meas_lab, de, warn, standout = self.inputs[loc]
            if f.suspect:
                self.by_neighbour.add(loc)
            self.why[loc] = dict(self.why.get(loc, {}), neighbour=bool(f.suspect))
            self.judge.judge(loc, exp_lab, meas_lab, de, warn or f.suspect,
                             standout=standout, live=False,
                             strip=c.strips[ix[loc]], reread_only=f.suspect)

    def _batch(self, locs, xyz_by_loc, *, strip_mode):
        c = self.chart
        ix = c.index()
        exyz = {loc: self.exp_xyz[ix[loc]] for loc in locs}
        changed = {}
        if self.applies:
            for loc in locs:
                self.nc.set_reading(loc, exyz[loc], xyz_by_loc[loc],
                                    c.strips[ix[loc]])
            changed = self._redraw_set()
        des = [de76(xyz_to_lab(exyz[l]), xyz_to_lab(xyz_by_loc[l])) for l in locs]
        fence = strip_outlier_fence(des) if (strip_mode and self.fence_on) else 0.0
        median = statistics.median(des) if des else 0.0
        for loc, de in zip(locs, des):
            warn = de >= self.limit and de >= fence
            hid = de >= self.limit and not warn
            if warn:
                self.by_limit.add(loc)
            if hid:
                self.fence_hid.add(loc)
            exp_lab = icc_xyz_to_lab(tuple(v / 100.0 for v in exyz[loc]))
            meas_lab = icc_xyz_to_lab(tuple(v / 100.0 for v in xyz_by_loc[loc]))
            standout = de - median if strip_mode else None
            self.inputs[loc] = (exp_lab, meas_lab, de, warn, standout)
            f = self.nc.finding(loc) if self.applies else None
            sus = bool(f is not None and f.suspect)
            if sus:
                self.by_neighbour.add(loc)
            self.why[loc] = {"limit": bool(warn), "neighbour": sus,
                             "fence_hid": bool(hid), "de": round(de, 2)}
            self.judge.judge(loc, exp_lab, meas_lab, de, warn or sus,
                             standout=standout, live=True,
                             strip=c.strips[ix[loc]], reread_only=sus)
        self._rejudge_changed(changed, set(locs))
        self.judge.rejudge()

    # ---- what is on screen -----------------------------------------------------
    def outlines(self) -> dict:
        """``{loc: "red" | "green" | "yellow" | "yellow_peer" |
        "yellow_learned"}``. A patch drawn green has no verdict in the
        judge's memory (it is not flagged), so it is taken from
        :meth:`corrected_locs`."""
        out = {}
        for loc, v in self.judge._verdicts.items():
            o = outline(v)
            if o:
                out[loc] = o
        for loc in self.corrected_locs():
            out.setdefault(loc, "green")
        return out

    def red_reason(self, loc: str) -> str:
        """Why *loc* is red now: "limit", "neighbour" or "both"."""
        w = self.why.get(loc, {})
        lim, nb = w.get("limit", False), w.get("neighbour", False)
        if lim and nb:
            return "both"
        return "limit" if lim else "neighbour" if nb else "other"

    def suspects(self) -> list:
        return self.nc.suspects() if self.applies else []

    def corrected_locs(self) -> list:
        """``TabMeasure.corrected_locs``."""
        last = getattr(self.judge, "_last", {})
        return PF.sorted_locs(loc for loc in self.judge.corrected
                              if loc not in last or not last[loc].flagged)

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

    def misread_summary(self, *, read_twice_active: bool = True,
                        tr=lambda s: s) -> str:
        """``TabMeasure._misread_summary`` line for line, in English (or
        through *tr*): what the window that closes the measurement shows
        under the reading times. Empty for a verification."""
        from workflow import measurement_messages as M
        if self.kind == "verification":
            return ""
        lines = []
        facts = self.summary_facts()
        if facts is not None:
            red, kept = facts["red"], facts["kept"]

            def listed(locs) -> str:
                return ", ".join(locs[:10]) + ("…" if len(locs) > 10 else "")
            if not red and not kept and not facts["checked"]:
                lines.append(tr(M._SUM_NB_NONE_CHECKED).format(total=facts["total"]))
            elif not red:
                lines.append(tr(M._SUM_NB_NONE))
            elif len(red) == 1:
                lines.append(tr(M._SUM_NB_RED_ONE).format(locs=red[0]))
            else:
                lines.append(tr(M._SUM_NB_RED).format(n=len(red), locs=listed(red)))
            if len(kept) == 1:
                lines.append(tr(M._SUM_NB_KEPT_ONE))
            elif kept:
                lines.append(tr(M._SUM_NB_KEPT).format(n=len(kept)))
            if 0 < facts["checked"] < facts["total"]:
                lines.append(tr(M._SUM_NB_PARTLY).format(
                    checked=facts["checked"], total=facts["total"]))
        fixed = self.corrected_locs()
        if len(fixed) == 1:
            lines.append(tr(M._SUM_CORRECTED_ONE).format(locs=fixed[0]))
        elif fixed:
            lines.append(tr(M._SUM_CORRECTED).format(
                n=len(fixed), locs=", ".join(fixed[:10])
                + ("…" if len(fixed) > 10 else "")))
        if read_twice_active:
            items = []
            for strip, like, choice in self.read_twice_log:
                key = {"reread": M._SUM_TWICE_REREAD,
                       "was_like": M._SUM_TWICE_WAS_LIKE}.get(choice, M._SUM_TWICE_KEPT)
                items.append(tr(key).format(strip=strip, like=like))
            if not items:
                lines.append(tr(M._SUM_TWICE_NONE))
            elif len(items) == 1:
                lines.append(tr(M._SUM_TWICE_ONE).format(list=items[0]))
            else:
                lines.append(tr(M._SUM_TWICE).format(n=len(items), list=", ".join(items)))
        return "\n".join(lines)
