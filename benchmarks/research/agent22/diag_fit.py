"""Agent 22 model-level diagnostic: how the shipped accurate grid fit treats
strip-misread rows. Per dataset: misread rows (truth), their residual in the
stiff scan, their robust weight, and the forward model error vs truth near the
grey axis (light / mid / dark), as-is vs oracle (strips removed from the data).

python diag_fit.py X3m:targen:2 ...   (cwd = agent22/tree)"""
import os, sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, os.getcwd())
from benchmarks.research import datasets as dsm, noise, colour
from benchmarks.research.printers import build_printers
from workflow.profile_engine.ti3_data import read_ti3
from workflow.profile_engine import builder
from workflow.profile_engine.accuracy import fit_forward_model_accurate
from workflow.profile_engine.metrics import delta_e_2000

P = build_printers()
W = Path(__file__).parent / "work" / "diag"; W.mkdir(parents=True, exist_ok=True)


def make(pid, kind, k, oracle):
    det = {}
    p = P[pid]
    from benchmarks.research import charts
    if kind == "september":
        chart = dsm.make_chart(p, 900, 11 + k)
    else:
        chart = charts.chart_for(p, "targen", 900, 11 + k)
    xyz, spec, mis = noise.measure(p, chart, level="pessimistic", seed=23 + k, detail=det,
                                   strip_prob=0.0 if oracle else None)
    f = dsm.write_ti3(W / f"{pid}-{kind}-{k}-{int(oracle)}.ti3", p, chart, xyz, spec)
    return f, det, chart


def fit(f, n):
    m = read_ti3(f)
    m.average_endpoints()
    grid = builder._A2B_GRID_34[1] if n >= 4 else builder._A2B_GRID_23[1]
    d = {}
    model, out, lam = fit_forward_model_accurate(
        m.device, m.lab_relative, grid=grid, base_lam=builder._fit_lambda(grid),
        curve_rounds=2, positioning=True, additive=m.is_additive, diag=d)
    return m, model, out, d


def grey_probe(p, n):
    """device values near the printer's grey axis: truth B2A of L* 20..98 is
    unknown here, so use CMY-equal (and K 0) device ramps as a proxy set plus
    random light near-neutral devices."""
    t = np.linspace(0, 1, 41)[:, None]
    if p.is_additive:
        return np.repeat(1 - t, 3, 1)
    d = np.zeros((41, n)); d[:, :3] = t * 0.9
    return d


for arg in sys.argv[1:]:
    pid, kind, k = arg.split(":"); k = int(k)
    p = P[pid]
    rep = {}
    for oracle in (False, True):
        f, det, chart = make(pid, kind, k, oracle)
        m, model, out, d = fit(f, p.n)
        truth = p.lab_rel(m.device)
        dev_eval = dsm_eval = None
        rng = np.random.default_rng(5)
        ev = rng.uniform(size=(4000, p.n))
        if p.tac is not None and not p.is_additive:
            from workflow.profile_engine.b2a import project_tac
            ev = project_tac(ev, p.tac / 100.0)
        e = delta_e_2000(model.predict(ev), p.lab_rel(ev))
        L = p.lab_rel(ev)[:, 0]
        g = grey_probe(p, p.n)
        eg = delta_e_2000(model.predict(g), p.lab_rel(g))
        r = {"a2b_med": float(np.median(e)), "a2b_p95": float(np.percentile(e, 95)),
             "a2b_p95_L>80": float(np.percentile(e[L > 80], 95)),
             "grey_ramp_max": float(eg.max()), "grey_ramp_mean": float(eg.mean()),
             "outliers_named": int(len(out))}
        if not oracle:
            mis = np.array(sorted(set(np.concatenate([np.array(s) for s in det["strips"]]).tolist())), int) if det["strips"] else np.array([], int)
            meas_err = delta_e_2000(m.lab_relative, truth)
            w = d["w_rob"]
            r["strips"] = len(det["strips"])
            r["strip_rows"] = int(len(mis))
            if len(mis):
                r["strip_true_err_med"] = float(np.median(meas_err[mis]))
                r["strip_rows_w0"] = int((w[mis] == 0).sum())
                r["strip_rows_wpartial"] = int(((w[mis] > 0) & (w[mis] < 0.999)).sum())
                r["strip_rows_w1"] = int((w[mis] >= 0.999).sum())
                r["w1_true_err"] = [round(float(v), 2) for v in meas_err[mis][w[mis] >= 0.999]]
                r["partial_true_err"] = [round(float(v), 2) for v in meas_err[mis][(w[mis] > 0) & (w[mis] < 0.999)]]
                r["scale"] = float(d["scale"])
            clean = np.setdiff1d(np.arange(len(w)), mis)
            r["clean_rows_w0"] = int((w[clean] == 0).sum())
        rep["oracle" if oracle else "asis"] = r
    print(arg, json.dumps(rep), flush=True)
