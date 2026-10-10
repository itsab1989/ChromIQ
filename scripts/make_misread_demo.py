#!/usr/bin/env python3
"""Demo data that triggers every kind of misread on every chart type (#182,
beta 17, Knut's test plan 6084756743).

    python scripts/make_misread_demo.py [destination]   # default ./demo-projects

*"Run tests on-screen on real app using demo data created to trigger on all
measurement misread error types on all types of charts."* This writes one
project, ``Demo-Misread-Tests``, with a REAL chart for each chart type (real
``targen`` patches laid out by ChromIQ's own engine, real page TIFFs, the
geometry the Measure tab draws its outlines on; the same pipeline as
``scripts/make_demo_projects.py``):

==========================  ===============================================
``runs/run1``               profiling chart with estimated colours
``runs/run2``               profiling chart made with a pre-conditioning
                            profile (``ACCURATE_EXPECTED_VALUES "true"``)
``verify-through/``         verification chart printed through the profile
``verify-fpg/``             verification chart filled From Profile Gamut
                            (in-gamut colours plus the 8 cube corners)
``cal/``                    calibration chart (grey, R, G, B, C, M, Y ramps)
==========================  ===============================================

and, beside each chart, ``<stem>.misreads.json``: a simulated printer's
readings of every patch and the misreads the protocol replays, each of them
chosen so that it trips exactly the test it is meant for at the default
thresholds (worked out with :func:`four_steps`, an implementation of Knut's
rule that is independent of the app's):

* ``gross``: one patch carries the reading of a far colour (past the patch
  error limit);
* ``small``: one patch read off by less than the patch error limit but more
  than the neighbour limit above its neighbours (the neighbour check);
* ``small2``: another such patch, re-read 3.6 ΔE*ab away from its first
  reading (the same-reading tolerance);
* ``small3``: a third, re-read correctly and then misread again (green, then
  red again);
* ``gamut``: a colour the printer really cannot reach: past the patch error
  limit, and every re-read gives the same reading (yellow);
* ``strip_offset``: a whole strip read off together (a light leak, a tipped
  instrument; the strip test);
* ``partial``: half a strip read off;
* ``out_of_step``: a strip whose readings are one patch late;
* ``wrong_strip``: a strip that carries another strip's readings.

The verification charts are judged against their profile's prediction in the
app; the demo's prediction is the chart's own expected colours (the driver
hands them to the Measure tab as the prediction), so the numbers stay the
ones written here.
"""
from __future__ import annotations

import json
import math
import random
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE))

NAME = "Demo-Misread-Tests"
#: icmD50, the white the engine's L*a*b* is computed against
_D50 = (0.9642, 1.0, 0.8249)

#: the defaults Knut approved (workflow/misread_settings.py), per chart type
DEFAULTS = {
    "estimated": dict(pel=95.0, strip=True, nl=10.0, nr=15.0),
    "accurate": dict(pel=20.0, strip=True, nl=5.0, nr=30.0),
    "verification": dict(pel=5.0, strip=False, nl=3.0, nr=30.0),
    "verification_fpg": dict(pel=5.0, strip=False, nl=3.0, nr=30.0),
    "calibration": dict(pel=95.0, strip=True, nl=10.0, nr=30.0),
}
#: how far each kind of misread is off (ΔE*ab), per chart type: "small"
#: lands between the neighbour limit and the patch error limit, "gamut" just
#: past the patch error limit where that limit is low, "offset" for a whole
#: strip.
SIZES = {
    "estimated": dict(small=16.0, gamut=None, offset=30.0),
    "accurate": dict(small=10.0, gamut=26.0, offset=26.0),
    "verification": dict(small=4.4, gamut=7.5, offset=7.5),
    "verification_fpg": dict(small=4.4, gamut=7.5, offset=7.5),
    "calibration": dict(small=16.0, gamut=None, offset=30.0),
}
FOLDERS = {"estimated": "runs/run1", "accurate": "runs/run2",
           "verification": "verify-through", "verification_fpg": "verify-fpg",
           "calibration": "cal"}


# ---- colour ------------------------------------------------------------------
def lab(xyz100):
    from workflow.neighbour_check import engine_lab
    return engine_lab(xyz100)


def xyz(lab_):
    L, a, b = lab_
    fy = (L + 16.0) / 116.0
    fx, fz = fy + a / 500.0, fy - b / 200.0

    def inv(t):
        return t ** 3 if t ** 3 > 216.0 / 24389.0 else (116.0 * t - 16.0) * 27.0 / 24389.0
    return tuple(max(0.0, inv(f) * w * 100.0)
                 for f, w in zip((fx, fy, fz), _D50))


def de(a, b):
    return math.dist(a, b)


# ---- Knut's four steps, written apart from the app ---------------------------
def four_steps(loc, exp_lab: dict, meas_lab: dict, *, radius: float,
               k: int = 4, min_n: int = 2, order: "dict | None" = None):
    """``(n, further)``: Knut's rule for *loc* among the read patches
    (*meas_lab* holds only read ones): its 2 to 4 nearest read patches in
    expected colour within *radius* (any strip), each one's error, their
    median, the patch's own error, own minus median. ``(n, None)`` when
    fewer than *min_n* neighbours. Ties go to the patch read first."""
    me = exp_lab[loc]
    # equal distances: the patch read first (*order*: loc -> reading index),
    # as ArgyllCMS charts repeat colours (a calibration chart's ramps all
    # start at the same white)
    order = order or {}
    cand = sorted((de(me, exp_lab[o]), order.get(o, 0), o)
                  for o in meas_lab if o != loc
                  and de(me, exp_lab[o]) <= radius)[:k]
    cand = [(d_, o) for d_, _i, o in cand]
    if len(cand) < min_n:
        return len(cand), None
    errs = sorted(de(meas_lab[o], exp_lab[o]) for _d, o in cand)
    n = len(errs)
    med = errs[n // 2] if n % 2 else (errs[n // 2 - 1] + errs[n // 2]) / 2
    return n, de(meas_lab[loc], exp_lab[loc]) - med


# ---- the chart files ----------------------------------------------------------
def read_ti2(path: Path) -> "list[dict]":
    fields, rows, fmt, data = [], [], False, False
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s == "BEGIN_DATA_FORMAT":
            fmt = True; continue
        if s == "END_DATA_FORMAT":
            fmt = False; continue
        if fmt:
            fields = s.split(); continue
        if s == "BEGIN_DATA":
            data = True; continue
        if s == "END_DATA":
            break
        if data and s:
            rows.append(s.replace('"', "").split())
    ix = {n: i for i, n in enumerate(fields)}
    out = []
    for r in rows:
        out.append({"sid": r[ix["SAMPLE_ID"]], "loc": r[ix["SAMPLE_LOC"]],
                    "rgb": [float(r[ix[c]]) for c in ("RGB_R", "RGB_G", "RGB_B")],
                    "exyz": [float(r[ix[c]]) for c in ("XYZ_X", "XYZ_Y", "XYZ_Z")]})
    return out


def write_ti3(path: Path, patches: "list[dict]", readings: dict) -> None:
    """A measurement of the chart in chartread's own shape."""
    from core.cgats_date import created_stamp
    out = ["CTI3", "", 'DESCRIPTOR "Argyll Calibration Target chart information 3"',
           'ORIGINATOR "Argyll chartread"', f'CREATED "{created_stamp()}"',
           'KEYWORD "DEVICE_CLASS"', 'DEVICE_CLASS "OUTPUT"',
           'KEYWORD "COLOR_REP"', 'COLOR_REP "RGB_XYZ"',
           "NUMBER_OF_FIELDS 8", "BEGIN_DATA_FORMAT",
           "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
           "END_DATA_FORMAT", f"NUMBER_OF_SETS {len(patches)}", "BEGIN_DATA"]
    for p in patches:
        x = readings[p["loc"]]
        out.append(f'{p["sid"]} "{p["loc"]}" {p["rgb"][0]:.4f} {p["rgb"][1]:.4f} '
                   f'{p["rgb"][2]:.4f} {x[0]:.4f} {x[1]:.4f} {x[2]:.4f}')
    out += ["END_DATA", ""]
    path.write_text("\n".join(out), encoding="utf-8")


def _ti1_from_rgb(path: Path, rgbs) -> None:
    """A ``.ti1`` of *rgbs* (0..100) with targen's own estimate as XYZ."""
    from workflow.patch_flags import targen_estimate_xyz
    out = ["CTI1", "", 'DESCRIPTOR "Argyll Calibration Target chart information 1"',
           'ORIGINATOR "ChromIQ misread demo"', 'CREATED "Fri Oct 09 12:00:00 2026"',
           'KEYWORD "APPROX_WHITE_POINT"', 'APPROX_WHITE_POINT "95.1 100.0 108.9"',
           'KEYWORD "COLOR_REP"', 'COLOR_REP "iRGB"',
           "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
           "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
           f"NUMBER_OF_SETS {len(rgbs)}", "BEGIN_DATA"]
    for n, rgb in enumerate(rgbs, start=1):
        x = [v * 100.0 for v in targen_estimate_xyz(rgb)]
        out.append(f"{n} {rgb[0]:.4f} {rgb[1]:.4f} {rgb[2]:.4f} "
                   f"{x[0]:.5f} {x[1]:.5f} {x[2]:.5f}")
    out += ["END_DATA", ""]
    path.write_text("\n".join(out), encoding="utf-8")


def _build(into: Path, stem: str, ti1: Path, *, seed: int) -> Path:
    """Lay *ti1* out with ChromIQ's engine, as the app does, and fold the
    layout into ``<stem>.channels.json`` (make_demo_projects._chart_files)."""
    from workflow.layout_engine.chart import build_chart
    from workflow.layout_engine.presets import LayoutRecipe
    into.mkdir(parents=True, exist_ok=True)
    base = into / stem
    if ti1 != base.with_suffix(".ti1"):
        shutil.copy2(ti1, base.with_suffix(".ti1"))
    kwargs = dict(instrument="i1", paper="A4", randomize=True, seed=seed)
    result = build_chart(base.with_suffix(".ti1"), base, **kwargs)
    strips = into / f"{stem}.strips.json"
    layout = json.loads(strips.read_text(encoding="utf-8")) if strips.exists() else {}
    layout.update({"engine": "chromiq", "engine_version": 1,
                   "seed": getattr(result, "seed", seed),
                   "color_rep": getattr(result, "color_rep", "RGB"),
                   "recipe": LayoutRecipe.from_build_kwargs(kwargs).to_dict(),
                   "margins_chosen_by_user": False})
    (into / f"{stem}.channels.json").write_text(
        json.dumps({"channels": ["r", "g", "b"], "layout": layout}),
        encoding="utf-8")
    strips.unlink(missing_ok=True)
    return base.with_suffix(".ti2")


# ---- the simulated printer and the misreads ------------------------------------
def _printer(kind: str, exp_lab, rng: random.Random):
    """A clean reading. Estimated colours are a rough guess of the print
    (lighter, less saturated, more so the more vivid), the others close."""
    L, a, b = exp_lab
    if kind in ("estimated", "calibration"):
        m = (L * 0.96 + 1.5, a * 0.86, b * 0.86)
        noise = 0.5
    elif kind == "accurate":
        m = (L + 0.6, a + 0.3, b - 0.4)
        noise = 0.5
    else:
        m = (L, a, b)
        noise = 0.35
    return tuple(v + rng.gauss(0.0, noise) for v in m)


def _direction(rng):
    v = [rng.gauss(0, 1) for _ in range(3)]
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def scenario(kind: str, ti2: Path) -> dict:
    patches = read_ti2(ti2)
    rng = random.Random(f"misread-{kind}")
    exp_lab = {p["loc"]: lab(p["exyz"]) for p in patches}
    clean_lab = {p["loc"]: _printer(kind, exp_lab[p["loc"]], rng)
                 for p in patches}
    d = DEFAULTS[kind]
    sz = SIZES[kind]
    strips: "dict[str, list]" = {}
    for p in patches:
        letter = "".join(c for c in p["loc"] if c.isalpha())
        strips.setdefault(letter, []).append(p["loc"])
    order = sorted(strips, key=lambda s: (len(s), s))

    def judged(loc, meas, radius):
        n, fu = four_steps(loc, exp_lab, meas, radius=radius)
        return n, fu

    # candidates: patches with 3 or 4 neighbours, well inside the chart
    def ok_for_small(loc):
        n, fu = judged(loc, clean_lab, d["nr"])
        return n >= 3 and fu is not None and abs(fu) < 1.5

    pool = [p["loc"] for p in patches if ok_for_small(p["loc"])]
    rng.shuffle(pool)
    taken: set = set()

    def pick(pred):
        """A patch for one misread: never in a strip another one uses (a
        strip re-read re-reads its every patch), never near another in
        colour (each is judged against clean neighbours)."""
        used = {"".join(c for c in t if c.isalpha()) for t in taken}
        for loc in pool:
            letter = "".join(c for c in loc if c.isalpha())
            if loc in taken or letter in used:
                continue
            if any(de(exp_lab[loc], exp_lab[t]) < 2.2 * d["nr"] for t in taken):
                continue
            if pred(loc):
                taken.add(loc)
                return loc
        raise SystemExit(f"{kind}: no patch fits")

    def off(loc, size, seed):
        r = random.Random(f"{kind}-{loc}-{seed}")
        u = _direction(r)
        return tuple(c + size * x for c, x in zip(clean_lab[loc], u))

    first = dict(clean_lab)
    plan = {}

    # small misreads: past the neighbour limit, under the patch error limit
    def small_ok(loc, size, seed):
        trial = dict(clean_lab)
        trial[loc] = off(loc, size, seed)
        n, fu = judged(loc, trial, d["nr"])
        e = de(trial[loc], exp_lab[loc])
        return fu is not None and fu > d["nl"] + 1.0 and e < d["pel"] - 0.3
    for name, seed in (("small", 1), ("small2", 2), ("small3", 3)):
        loc = pick(lambda L, s=seed: small_ok(L, sz["small"], s))
        first[loc] = off(loc, sz["small"], seed)
        plan[name] = loc

    # gross: the reading of the colour furthest from it on the chart
    def gross_ok(loc):
        far = max(patches, key=lambda p: de(exp_lab[loc], clean_lab[p["loc"]]))
        return de(exp_lab[loc], clean_lab[far["loc"]]) >= d["pel"] + 3
    g = pick(gross_ok)
    far = max(patches, key=lambda p: de(exp_lab[g], clean_lab[p["loc"]]))
    first[g] = clean_lab[far["loc"]]
    plan["gross"] = g

    # gamut: a real shortfall, past a low patch error limit; on charts with
    # estimated colours a vivid patch the printer falls 40 short of
    gsize = sz["gamut"] if sz["gamut"] is not None else 40.0

    def gamut_ok(loc):
        e = exp_lab[loc]
        return math.hypot(e[1], e[2]) > 35
    y = pick(gamut_ok)
    e = exp_lab[y]
    c = math.hypot(e[1], e[2])
    short = (e[0], e[1] * (1 - gsize / c), e[2] * (1 - gsize / c))
    clean_lab[y] = first[y] = short
    plan["gamut"] = y

    # strips (a second measurement, so the single patches stay clean)
    strip_set = dict(clean_lab)
    free = [s for s in order if len(strips[s]) >= 6]
    if len(free) < 4:
        raise SystemExit(f"{kind}: {len(free)} strips, 4 are needed")
    step = max(1, len(free) // 4)
    t, u, v, pp = (free[(i * step) % len(free)] for i in range(4))
    # the strip whose readings the wrong strip carries: any other one
    w = next(s for s in free if s != v)
    shift = (sz["offset"] / math.sqrt(3),) * 3
    for loc in strips[t]:
        strip_set[loc] = tuple(a + b for a, b in zip(clean_lab[loc], shift))
    half = strips[pp][: len(strips[pp]) // 2]
    for loc in half:
        strip_set[loc] = tuple(a + b for a, b in zip(clean_lab[loc], shift))
    us = strips[u]
    for j, loc in enumerate(us):
        strip_set[loc] = clean_lab[us[j + 1]] if j + 1 < len(us) else clean_lab[us[0]]
    for a_, b_ in zip(strips[v], strips[w]):
        strip_set[a_] = clean_lab[b_]
    plan.update({"strip_offset": t, "partial": pp, "partial_locs": half,
                 "out_of_step": u, "wrong_strip": v, "wrong_strip_from": w})

    # a misread again after the correction: checked to be one
    loc3 = plan["small3"]
    bad_again = None
    for seed in range(9, 400):
        cand = off(loc3, sz["small"] + (seed % 3) * 0.5, seed)
        trial = dict(first)
        trial[loc3] = cand
        n, fu = four_steps(loc3, exp_lab, trial, radius=d["nr"])
        if fu is not None and fu > d["nl"] + 1.0 and \
                de(cand, exp_lab[loc3]) < d["pel"] - 0.3 and \
                de(cand, first[loc3]) > 4.0:
            bad_again = cand
            break
    assert bad_again is not None, kind
    # the re-reads the protocol replays
    rereads = {
        "small_same": off(plan["small"], sz["small"], 1),
        "small_same_jitter": tuple(c + 0.3 for c in off(plan["small"],
                                                          sz["small"], 1)),
        "small2_3_6": tuple(c + 3.6 / math.sqrt(3)
                            for c in off(plan["small2"], sz["small"], 2)),
        "small3_good": clean_lab[plan["small3"]],
        "small3_bad_again": bad_again,
        "gross_good": clean_lab[g],
        "gross_bad_again": clean_lab[min(
            patches, key=lambda p: -de(exp_lab[g], clean_lab[p["loc"]])
            if p["loc"] != far["loc"] else 0)["loc"]],
        "gamut_same": tuple(c + 0.4 for c in short),
    }
    # the strip-offset strip: one patch re-read the same, one correct
    rereads["offset_same"] = strip_set[strips[t][1]]
    rereads["offset_good"] = clean_lab[strips[t][2]]
    plan["offset_same_loc"] = strips[t][1]
    plan["offset_good_loc"] = strips[t][2]

    def as_xyz(d_):
        return {k_: [round(x, 5) for x in xyz(v_)] for k_, v_ in d_.items()}

    facts = {}
    for name in ("small", "small2", "small3", "gross", "gamut"):
        loc = plan[name]
        n, fu = four_steps(loc, exp_lab, first, radius=d["nr"])
        facts[name] = {"loc": loc, "de": round(de(first[loc], exp_lab[loc]), 2),
                       "neighbours": n,
                       "further": None if fu is None else round(fu, 2)}
    return {
        "kind": kind, "chart": ti2.name, "strips": order,
        "strip_locs": strips, "defaults": d, "plan": plan, "facts": facts,
        "patches": {p["loc"]: {"sid": p["sid"], "rgb": p["rgb"],
                               "exyz": p["exyz"]} for p in patches},
        "clean": as_xyz(clean_lab), "first": as_xyz(first),
        "strip_set": as_xyz(strip_set),
        "rereads": {k_: [round(x, 5) for x in xyz(v_)]
                    for k_, v_ in rereads.items()},
    }


# ---- the project -----------------------------------------------------------------
def build(dest: Path) -> Path:
    from make_demo_projects import _argyll, _meta, _run_tool, _write_manifest
    root = dest / NAME
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    stem = NAME
    work = root / ".build"
    work.mkdir()
    # the profiling chart: a real targen patch set
    _run_tool([_argyll("targen"), "-v0", "-d2", "-G", "-f400", "base"],
              cwd=work, timeout=300)
    charts = {}
    charts["estimated"] = _build(root / FOLDERS["estimated"], stem,
                                 work / "base.ti1", seed=17)
    # made with a pre-conditioning profile: what targen -c marks its chart
    # with; the expected colours are the chart's own (the demo's printer is
    # close to them)
    acc = root / FOLDERS["accurate"]
    acc.mkdir(parents=True)
    for f in charts["estimated"].parent.glob(f"{stem}.*"):
        shutil.copy2(f, acc / f.name)
    for ext in (".ti1", ".ti2"):
        p = acc / f"{stem}{ext}"
        txt = p.read_text(encoding="utf-8")
        txt = txt.replace("NUMBER_OF_FIELDS",
                          'KEYWORD "ACCURATE_EXPECTED_VALUES"\n'
                          'ACCURATE_EXPECTED_VALUES "true"\nNUMBER_OF_FIELDS', 1)
        p.write_text(txt, encoding="utf-8")
    charts["accurate"] = acc / f"{stem}.ti2"
    # verification, through the profile: the profiling chart's patches
    vt = root / FOLDERS["verification"]
    vt.mkdir(parents=True)
    for f in charts["estimated"].parent.glob(f"{stem}.*"):
        shutil.copy2(f, vt / f.name)
    charts["verification"] = vt / f"{stem}.ti2"
    # verification From Profile Gamut: in-gamut colours and the 8 corners
    r = random.Random(5)
    rgbs = [(a, b, c) for a in (0, 100) for b in (0, 100) for c in (0, 100)]
    while len(rgbs) < 240:
        rgbs.append(tuple(round(r.uniform(8, 92), 1) for _ in range(3)))
    _ti1_from_rgb(work / "fpg.ti1", rgbs)
    charts["verification_fpg"] = _build(root / FOLDERS["verification_fpg"], stem,
                                        work / "fpg.ti1", seed=23)
    # calibration: grey, R, G, B, C, M and Y ramps of 21 steps
    ramp = []
    for i in range(21):
        v = i * 5.0
        ramp += [(v, v, v), (v, 0.0, 0.0), (0.0, v, 0.0), (0.0, 0.0, v),
                 (0.0, v, v), (v, 0.0, v), (v, v, 0.0)]
    _ti1_from_rgb(work / "cal.ti1", ramp)
    charts["calibration"] = _build(root / FOLDERS["calibration"],
                                   f"{stem}-cal", work / "cal.ti1", seed=29)
    shutil.rmtree(work)

    for kind, ti2 in charts.items():
        sc = scenario(kind, ti2)
        sc["chart_rel"] = str(ti2.relative_to(root))
        ti2.with_suffix(".misreads.json").write_text(
            json.dumps(sc, indent=1), encoding="utf-8")
        # the first reading, misreads and all, as the measurement on disk
        patches = [{"sid": v["sid"], "loc": k, "rgb": v["rgb"]}
                   for k, v in sc["patches"].items()]
        write_ti3(ti2.with_suffix(".ti3"), patches, sc["first"])

    _write_manifest(root, NAME, [
        {"id": "run1", "created_at": "2026-10-09T12:00:00", "parent": None},
        {"id": "run2", "created_at": "2026-10-09T12:30:00", "parent": "run1"},
    ], "run1", 3)
    _meta(root / "runs/run1", "run1", instrument="i1")
    _meta(root / "runs/run2", "run2", instrument="i1", parent_run="run1")
    (root / "README.md").write_text(
        "# Demo-Misread-Tests\n\nMade by `scripts/make_misread_demo.py` for "
        "the beta-17 test plan (#182, Knut 6084756743). Each chart folder "
        "holds the chart, a measurement with the misreads already in it "
        "(`*.ti3`) and `*.misreads.json`, the readings the on-screen protocol "
        "replays.\n", encoding="utf-8")
    return root


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dest = Path(argv[0]) if argv else _HERE.parent / "demo-projects"
    root = build(dest)
    for f in sorted(root.rglob("*.misreads.json")):
        sc = json.loads(f.read_text(encoding="utf-8"))
        print(f"{sc['kind']:18} {sc['chart_rel']:40} "
              + ", ".join(f"{k} {v['loc']} ΔE {v['de']} further {v['further']}"
                          for k, v in sc["facts"].items()))
    print(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
