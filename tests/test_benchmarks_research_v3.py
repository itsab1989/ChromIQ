"""Battery v3 (Agent 16, 2026-10-04): one test per fix of protocol v3.

A  sealed confirmatory set: new physics (Z family), secret seed, hashes only
   in the repository, refuses to be scored before the orchestrator unseals.
C  charts ChromIQ really produces (targen at its defaults, -s 0, no -l).
B  statistics: measured per-engine seed term (larger of A and B), means as
   means, claims only from sealed rows on primary charts, per-ink-count
   breakdown that cannot hide 5-7 inks.
R  readers: lcms with application flags, Ghostscript as a RIP (BPC off, and
   BPC on reported separately), B2A-only readers handled by the metrics.
D  development printers: Agent 13's XKH and XKB in the battery, unchanged.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from benchmarks.research import charts, colour, noise, zfamily as Z
from benchmarks.research.printers import build_printers

ARGYLL = Path("/Applications/Argyll/bin/icclu")
TARGEN = Path("/Applications/Argyll/bin/targen")
HAS_GS = shutil.which("gs") is not None


@pytest.fixture(scope="module")
def printers():
    return build_printers()


# ---------------------------------------------------------------------------
# A: the Z family and the sealed set
# ---------------------------------------------------------------------------

def test_km_film_has_the_beer_lambert_limit_without_scattering():
    lam = np.linspace(400, 700, 7)
    K = np.full_like(lam, 0.8)
    Rg = np.full_like(lam, 0.9)
    np.testing.assert_allclose(Z.km_film(K, np.zeros_like(K), Rg), 0.9 * np.exp(-1.6), rtol=1e-4)
    # scattering makes a dark film lighter, never darker
    assert np.all(Z.km_film(K, np.full_like(K, 0.2), Rg) > 0.9 * np.exp(-1.6))


def test_dot_off_dot_inks_share_paper_before_they_overlap():
    combos = Z.all_combos(3)
    w = Z.dot_off_dot(np.array([[0.3, 0.4, 0.2], [0.6, 0.6, 0.0]]), len(combos))
    np.testing.assert_allclose(w.sum(1), 1.0)
    single = combos.sum(1) == 1
    # total 90 %: no overlap at all, 10 % paper
    assert w[0, combos.sum(1) >= 2].sum() == pytest.approx(0.0, abs=1e-12)
    assert w[0, combos.sum(1) == 0].sum() == pytest.approx(0.1)
    # total 120 %: exactly the excess overlaps, no paper left
    assert w[1, combos.sum(1) == 2].sum() == pytest.approx(0.2)
    assert w[1, combos.sum(1) == 0].sum() == pytest.approx(0.0, abs=1e-12)
    assert w[1, single].sum() == pytest.approx(0.8)


def test_the_tone_curve_features_are_jumps_and_kinks_not_reversals():
    d = np.linspace(0, 1, 2001)
    t = {"gain": 0.2, "shape": [1.2, 1.4], "min_dot": 0.03, "screen": [0.15, 0.05],
         "kink": [0.5, 0.7]}
    a = Z.tone(d, t)
    assert a[0] == 0.0 and a[-1] == pytest.approx(1.0)
    assert np.all(np.diff(a) >= -1e-12)                       # monotone
    assert a[d < 0.03].max() == 0.0 and a[a > 0].min() > 0.015    # min-dot jump
    jump = np.max(np.diff(a))
    assert jump > 0.01                                          # the steps are real


def test_a_light_ink_hand_off_rises_then_falls_while_the_dark_ink_starts():
    v = np.linspace(0, 1, 101)
    light, dark = Z.handoff(v, {"peak": 0.4, "residual": 0.25, "onset": 0.3, "power": 1.0})
    assert light.argmax() == 40 and light[-1] == pytest.approx(0.25)
    assert dark[v < 0.3].max() == 0.0 and dark[-1] == pytest.approx(1.0)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_every_slot_draws_a_plausible_printer_from_a_public_seed(seed):
    from benchmarks.research import sealed as S
    for slot in S.SLOTS:
        p = Z.ZTruth(S.draw_slot(f"public-preview-{seed}".encode(), slot))
        res = S.plausibility(p)
        assert S.checks_passed(res), (slot["id"], {k: v for k, v in res.items() if not v})
        assert p.device_rep == slot["device_rep"]


def test_the_z_family_is_not_either_known_family(printers):
    """Structural difference, measured: a Z printer's two-ink overprint
    cannot be reproduced by Demichel + Yule-Nielsen from its own primaries
    with any n, unlike an S printer (which IS that model)."""
    from benchmarks.research import sealed as S
    p = Z.ZTruth(S.draw_slot(b"public-preview-4", S.SLOTS[3]))
    lam = colour.LAM_1NM

    def best_ynsn_error(pr):
        a = np.linspace(0.05, 0.95, 10)
        dev = np.zeros((len(a), pr.n))
        dev[:, 0] = a
        dev[:, 1] = a
        R = pr.reflectance(dev, lam)
        prims = pr.reflectance(np.array([[0, 0] + [0] * (pr.n - 2), [1, 0] + [0] * (pr.n - 2),
                                         [0, 1] + [0] * (pr.n - 2), [1, 1] + [0] * (pr.n - 2)],
                                        float), lam)
        best = np.inf
        # coverage free per point (optimistic for YNSN): grid search a_eff
        for nu in (1.0, 1.5, 2.0, 3.0, 5.0, 8.0):
            P = prims ** (1 / nu)
            err = 0.0
            for k in range(len(a)):
                cands = np.linspace(0, 1, 201)
                w = np.stack([(1 - cands) ** 2, cands * (1 - cands), cands * (1 - cands), cands ** 2], 1)
                model = (w @ P) ** nu
                err += np.min(np.abs(model - R[k]).max(1))
            best = min(best, err / len(a))
        return best
    s3 = printers["S3"]
    e_s, e_z = best_ynsn_error(s3), best_ynsn_error(p)
    assert e_s < 0.004                          # S is that model (plus a flare term)
    assert e_z > 3 * e_s


def test_the_print_field_is_smooth_and_small(tmp_path):
    from benchmarks.research import sealed as S
    params = S.draw_slot(b"public-preview-1", S.SLOTS[3])
    g = Z.print_field(params, 1617)
    assert np.all(np.abs(g - 1.0) < 0.03)
    assert np.std(np.diff(g)) < np.std(g) * 3          # smooth, not white noise


def test_row_gain_none_leaves_measure_unchanged(printers):
    from benchmarks.research.datasets import make_chart
    chart = make_chart(printers["S3"], 200, 11)
    a = noise.measure(printers["S3"], chart, level="typical", seed=23)
    b = noise.measure(printers["S3"], chart, level="typical", seed=23,
                      row_gain=np.ones(len(chart)))
    np.testing.assert_array_equal(a[0], b[0])
    np.testing.assert_array_equal(a[2], b[2])


SUBSET = ["Z03", "Z04"]


def _gen(tmp_path, seed=b"public-test-seed"):
    from benchmarks.research import sealed as S
    slots = [s for s in S.SLOTS if s["id"] in SUBSET]
    return S.generate(seed, tmp_path, slots=slots)


@pytest.mark.skipif(not TARGEN.exists(), reason="ArgyllCMS not installed")
def test_sealing_is_deterministic_and_the_manifest_holds_hashes_only(tmp_path):
    a = _gen(tmp_path / "a")
    b = _gen(tmp_path / "b")
    assert a == b
    c = _gen(tmp_path / "c", seed=b"another-seed")
    assert [s["params_sha256"] for s in c["slots"]] != [s["params_sha256"] for s in a["slots"]]
    text = json.dumps(a)
    for secret_key in ('"inks"', '"paper": {', '"handoff"', '"pooling"', '"bands"', '"tone"'):
        assert secret_key not in text
    for s in a["slots"]:
        assert len(s["params_sha256"]) == 64
        for d in s["datasets"]:
            assert len(d["ti3_sha256"]) == 64


@pytest.mark.skipif(not TARGEN.exists(), reason="ArgyllCMS not installed")
def test_a_sealed_set_cannot_be_scored_before_the_orchestrator_unseals_it(tmp_path):
    from benchmarks.research import sealed as S
    man = _gen(tmp_path)
    (tmp_path / "MANIFEST.json").write_text(json.dumps(man), encoding="utf-8")
    with pytest.raises(PermissionError):
        S.load_datasets(tmp_path, tmp_path / "work")
    assert S.main(["unseal", str(tmp_path), "--by", "agent15", "--reason", "x"]) == 2
    assert not S.is_unsealed(tmp_path)
    assert S.main(["unseal", str(tmp_path), "--by", "orchestrator", "--reason", "FINAL"]) == 0
    ds = S.load_datasets(tmp_path, tmp_path / "work")
    assert len(ds) == 2 * sum(len(s["charts"]) for s in S.SLOTS if s["id"] in SUBSET)
    assert all(d.info["role"] == "sealed-confirmatory" for _, d in ds)
    assert "unsealed by orchestrator" in (tmp_path / "UNSEAL-LOG.md").read_text(encoding="utf-8")


@pytest.mark.skipif(not TARGEN.exists(), reason="ArgyllCMS not installed")
def test_verify_catches_a_changed_measurement(tmp_path, monkeypatch):
    from benchmarks.research import sealed as S
    seed = b"public-verify-seed"
    monkeypatch.setattr(S, "SLOTS", [s for s in S.SLOTS if s["id"] in SUBSET])
    man = S.generate(seed, tmp_path)
    (tmp_path / "SEED").write_bytes(seed)
    (tmp_path / "MANIFEST.json").write_text(json.dumps(man), encoding="utf-8")
    assert S.main(["verify", str(tmp_path), "--manifest", ""]) == 0
    f = tmp_path / "data" / man["slots"][0]["datasets"][0]["ti3"]
    f.write_text(f.read_text(encoding="utf-8").replace("END_DATA", "1 0 0 0 0 0 0\nEND_DATA", 1),
                 encoding="utf-8")
    assert S.main(["verify", str(tmp_path), "--manifest", ""]) == 1


def test_the_repository_manifest_seals_twelve_printers_and_no_parameters():
    from benchmarks.research import sealed as S
    if not S.REPO_MANIFEST.exists():
        pytest.skip("not sealed yet")
    man = json.loads(S.REPO_MANIFEST.read_text(encoding="utf-8"))
    assert [s["id"] for s in man["slots"]] == [s["id"] for s in S.SLOTS]
    assert man["plausibility"]["failed"] == 0
    assert len(man["seed_commitment"]) == 64
    assert '"inks"' not in S.REPO_MANIFEST.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# C: charts
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", [200, 400, 560, 900, 1120, 1617, 3000])
def test_auto_neutrals_match_the_app(n):
    from workflow.chart_creator import manual_neutrals
    assert charts.chromiq_auto_neutrals(n) == manual_neutrals(n)


def test_targen_runs_at_chromiq_defaults_without_ramps_or_ink_limit():
    a = charts.targen_args("CMYK", 900)
    assert "-G" in a and any(x.startswith("-g") for x in a)
    assert not any(x.startswith(("-s", "-l")) for x in a)
    assert a[0] == "-d4"
    assert charts.targen_args("CMYKOV", 900)[:3] == ["-d4", "-D5", "-D9"]


@pytest.mark.parametrize("rep, n", [("RGB", 900), ("CMYK", 900), ("CMYKOGV", 1617),
                                    ("CMYKcm", 1120)])
def test_the_committed_targen_charts_are_what_chromiq_would_print(rep, n):
    f = charts.DATA / f"{charts.chart_name(rep, n)}.ti1"
    assert f.exists()
    text = f.read_text(encoding="utf-8")
    assert f'CHROMIQ_BENCH_COMMAND "targen {" ".join(charts.targen_args(rep, n))}"' in text
    got_rep, dev = charts.read_ti1(f)
    assert got_rep == rep and len(dev) == n


def test_a_chromiq_default_chart_has_almost_no_light_single_ink_patches():
    """Agent 13 T1: with -s 0 each ink gets a handful of single-ink patches
    and none at or below 12 %; the ramp-rich September chart has 11 each."""
    _, dev = charts.read_ti1(charts.DATA / "targen-CMYK-n900.ti1")
    c = charts.composition(dev, False)
    assert max(c["single_ink_per_channel"]) <= 8
    assert sum(c["single_ink_le12_per_channel"]) == 0
    from benchmarks.research.datasets import make_chart
    sept = charts.composition(make_chart(build_printers()["X3"], 900, 11), False)
    assert min(sept["single_ink_per_channel"]) >= 10


def test_the_september_chart_can_veto_but_never_carry_a_claim():
    assert charts.CHART_ROLE == {"targen": "primary", "ecg": "primary",
                                 "september": "robustness"}


# ---------------------------------------------------------------------------
# B: statistics
# ---------------------------------------------------------------------------

def _row(**kw):
    r = {"dataset": "Z04", "variant": "typical-targen900", "reader": "argyll",
         "reader_group": "cmm", "endpoint": "b2a.p95", "role": "sealed", "level": "typical",
         "chart": "targen", "chart_role": "primary", "ink_class": "CMYK", "a": 1.0,
         "b": 0.7, "diff": -0.3, "ci95": [-0.4, -0.2], "p": 1e-9, "rel": -0.3}
    r.update(kw)
    return r


def test_the_minimum_effect_uses_the_larger_measured_seed_sd_of_the_two_engines():
    from benchmarks.research import stats3
    table = {"accurate|typical|CMYK|b2a.p95": 0.265, "colprof|typical|CMYK|b2a.p95": 0.04}
    r = _row()
    stats3.minimum_effect(r, table, "colprof", "accurate")
    assert r["min_effect"] == pytest.approx(0.53)
    assert r["seed_sd_source"].startswith("measured:accurate")
    # a class nobody measured: the engine's largest SD over classes (conservative)
    r = _row(ink_class="7 inks")
    stats3.minimum_effect(r, table, "colprof", "accurate")
    assert r["min_effect"] == pytest.approx(0.53) and "fallback" in r["seed_sd_source"]
    # no table at all: the v2.1 placeholder term
    r = _row()
    stats3.minimum_effect(r, None, "colprof", "accurate")
    assert r["min_effect"] == pytest.approx(0.10) and r["seed_sd_source"] == "placeholder"


def test_means_are_endpoints_of_their_own():
    from benchmarks.research import stats3
    eps = {f"{k}.{s}" for k, s in stats3.ENDPOINTS}
    assert {"a2b.mean", "b2a.mean", "neutral_de.mean"} <= eps


def test_only_sealed_rows_on_a_primary_chart_can_carry_a_claim():
    from benchmarks.research import stats3
    rows = [_row(), _row(role="development"), _row(chart="september", chart_role="robustness",
                                                   variant="typical-september900")]
    stats3.decide(rows, "colprof", "accurate", None)
    assert [r["verdict"] for r in rows] == ["BETTER"] * 3
    assert [r["claim_eligible"] for r in rows] == [True, False, False]


def test_a_loss_on_a_development_printer_still_fails_the_no_regression_test():
    from benchmarks.research import stats3
    rows = [_row(role="development", diff=0.3, b=1.3, ci95=[0.2, 0.4])]
    stats3.decide(rows, "colprof", "accurate", None)
    nr = stats3.no_regression(rows)
    assert not nr["pass"] and nr["worse"]


def test_bpc_rows_are_reported_but_never_gate():
    from benchmarks.research import stats3
    rows = [_row(reader="ghostscript-bpc", reader_group="bpc", diff=0.3, b=1.3, ci95=[0.2, 0.4])]
    stats3.decide(rows, "colprof", "accurate", None)
    assert rows[0]["verdict_per_printer_endpoint"] == "WORSE"
    assert stats3.no_regression(rows)["pass"]


def test_the_per_ink_count_breakdown_says_when_a_class_is_not_covered():
    from benchmarks.research import stats3
    rows = [_row(dataset="X3")]
    stats3.decide(rows, "colprof", "accurate", None)
    res = {"datasets": [{"name": "X3", "n_channels": 4, "color_rep": "CMYK_XYZ"},
                        {"name": "X7", "n_channels": 7, "color_rep": "CMYKRGB_XYZ"},
                        {"name": "X8", "n_channels": 6, "color_rep": "CMYKcm_XYZ"}]}
    b = stats3.breakdown(rows, "colprof", "accurate", res)
    assert b["classes"]["CMYK"]["rows"] == 1
    assert "not_covered" in b["classes"]["7 inks"]
    assert "not_covered" in b["classes"]["CMYK+light (6)"]


def test_ramp_seed_verdicts_never_pool_two_noise_levels():
    from benchmarks.research import stats3
    rows = []
    for lvl in ("typical", "pessimistic"):
        for k in range(10):
            rows.append(_row(endpoint="neutral_hi.mean", variant=f"seed{k}-{lvl}-targen900",
                             level=lvl, diff=0.2 if lvl == "typical" else -0.2,
                             min_effect=0.05))
    g = stats3.ramp_seed_verdicts(rows)
    assert len(g) == 2 and {x["level"] for x in g} == {"typical", "pessimistic"}
    assert {x["verdict"] for x in g} == {"WORSE", "BETTER"}


def test_variants_parse_into_level_chart_and_seed():
    from benchmarks.research.stats3 import split_variant, ink_class
    assert split_variant("seed3-pessimistic-ecg1617") == {
        "seed": 3, "level": "pessimistic", "chart": "ecg", "patches": 1617}
    assert split_variant("typical-targen900")["chart"] == "targen"
    assert ink_class(3, "iRGB_XYZ") == "RGB" and ink_class(5, "CMYKO_XYZ") == "5 inks"


# ---------------------------------------------------------------------------
# R: readers
# ---------------------------------------------------------------------------

def _smooth_profile(tmp_path, n=4, rep="CMYK"):
    """A tiny engine-written profile with SMOOTH tables (A2B: a made-up
    printer; B2A: its rough inverse), so interpolation kernels agree."""
    from workflow.profile_engine import icc_writer as icw
    g = 9
    ax = np.linspace(0, 1, g)
    mesh = np.stack(np.meshgrid(*([ax] * n), indexing="ij"), -1).reshape(-1, n)
    L = 100 - 85 * np.clip(mesh.sum(1) / 2.2, 0, 1)
    a = 40 * (mesh[:, 1] - mesh[:, 0])
    b = 40 * (mesh[:, 1] - mesh[:, 2]) if n > 2 else 0 * L
    a2b = icw.make_mft2(n, 3, g, icw.lab_to_u16(np.column_stack([L, a, b])))
    lg = np.stack(np.meshgrid(np.linspace(0, 100, 17), np.linspace(-128, 127, 17),
                              np.linspace(-128, 127, 17), indexing="ij"), -1).reshape(-1, 3)
    dev = np.zeros((len(lg), n))
    dev[:, :3] = np.clip((100 - lg[:, :1]) / 100 * np.array([0.8, 0.7, 0.7]), 0, 1)
    if n > 3:
        dev[:, 3] = np.clip((60 - lg[:, 0]) / 60, 0, 1)
    b2a = icw.make_mft2(3, n, 17, icw.device_to_u16(dev))
    spec = icw.ProfileSpec(n_channels=n, description="v3 reader probe", color_rep=rep)
    return icw.write_profile(tmp_path / f"probe-{rep}.icc", spec,
                             {"A2B0": a2b, "A2B1": "A2B0", "A2B2": "A2B0",
                              "B2A0": b2a, "B2A1": "B2A0", "B2A2": "B2A0"})


LAB = np.array([[100.0, 0, 0], [80.0, 5, -5], [55.0, -10, 20], [30.0, 0, 0], [15.0, 3, 3]])


def test_lcms_with_application_flags_reads_like_the_table(tmp_path):
    from benchmarks.research import cmm
    try:
        cmm._lcms()
    except cmm.LcmsUnavailable as e:   # CI triage 37292451150, B-3
        pytest.skip(f"benchmark lcms reader unavailable here: {e}")
    p = _smooth_profile(tmp_path)
    ref = cmm.b2a(p, LAB, "lcms")
    app = cmm.b2a(p, LAB, "lcms-app")
    np.testing.assert_allclose(app, ref, atol=0.01)
    np.testing.assert_allclose(app[0], 0.0, atol=0.005)           # paper: (almost) no ink
    d = np.array([[0, 0, 0, 0], [0.3, 0.2, 0.1, 0.0], [0.5, 0.5, 0.5, 0.5]])
    np.testing.assert_allclose(cmm.a2b(p, d, "lcms-app"), cmm.a2b(p, d, "lcms"), atol=0.15)


@pytest.mark.skipif(not HAS_GS, reason="Ghostscript not installed")
def test_ghostscript_reads_the_b2a_like_a_cmm_and_bpc_moves_the_dark_end(tmp_path):
    from benchmarks.research import cmm
    p = _smooth_profile(tmp_path)
    gs = cmm.b2a(p, LAB, "ghostscript")
    np.testing.assert_allclose(gs, cmm.b2a(p, LAB, "lcms"), atol=0.01)
    np.testing.assert_allclose(gs[0], 0.0, atol=0.005)
    bpc = cmm.b2a(p, LAB, "ghostscript-bpc")
    assert np.abs(bpc - gs)[3:].max() > 0.01        # BPC acts in the dark end


def test_b2a_only_readers_are_declared_and_rip_scope_is_rgb_and_cmyk(tmp_path):
    from benchmarks.research import cmm
    assert not cmm.supports("ghostscript", "a2b")
    assert cmm.supports("ghostscript", "b2a")
    with pytest.raises(cmm.ReaderUnsupported):
        cmm.a2b(_smooth_profile(tmp_path), np.zeros((1, 4)), "ghostscript")
    assert set(cmm.READERS_V3) >= {"colorsync", "lcms-app", "ghostscript", "ghostscript-bpc"}


@pytest.mark.skipif(not HAS_GS, reason="Ghostscript not installed")
def test_the_metrics_score_a_b2a_only_reader_without_a2b(tmp_path, printers):
    from benchmarks.research import datasets as dsm, metrics
    p = _smooth_profile(tmp_path)
    pr = printers["X3"]
    ds = dsm.Dataset(name="X3", kind="synthetic", ti3=tmp_path / "none.ti3", n_channels=4,
                     color_rep="CMYK_XYZ", ink_limit=300.0, printer=pr)
    sink: dict = {}
    sc = metrics.score(p, ds, "ghostscript", metrics.Truth(printer=pr), n_eval=400,
                       light=True, sink=sink)
    assert sc["a2b_unsupported"] and "a2b" not in sc and "roundtrip" not in sc
    assert "b2a" in sc and "neutral" in sc and "a2b" not in sink and "b2a" in sink


# ---------------------------------------------------------------------------
# D: development printers and the reachable black
# ---------------------------------------------------------------------------

def test_agent13s_uneven_printers_are_in_the_battery_unchanged(printers):
    d = np.array([[0.2, 0.0, 0.0, 0.0], [0.35, 0.0, 0.0, 0.0], [0.6, 0.6, 0.6, 0.6],
                  [1.0, 1.0, 1.0, 0.0]])
    xkh = printers["XKH"].lab_rel(d)
    # the hand-off: cyan ramp L* 85.7 at 0.2 (Agent 13 K1 text), slope breaks at 0.3/0.4
    assert xkh[0, 0] == pytest.approx(85.7, abs=0.1)
    xkb = printers["XKB"]
    tot = np.linspace(2.0, 3.0, 11)
    L = xkb.lab_rel(np.repeat(tot[:, None] / 4, 4, 1))[:, 0]
    assert np.max(np.diff(L)) > 0.3                 # the dark end LIGHTENS (bronzing)


def test_the_reachable_black_is_found_on_a_printer_whose_dark_end_lightens(printers):
    from benchmarks.research import metrics
    p = printers["XKB"]
    r = metrics.reachable_black(metrics.Truth(printer=p), 4, False, 300.0)
    # Agent 13: the darkest neutral under the limit is L* 7.2 near 226 %
    assert 6.0 <= r["darkest_neutral_L"] <= 7.6
    assert 200 <= r["darkest_neutral_ink_pct"] <= 260


# ---------------------------------------------------------------------------
# targets v2 and the commercial comparison
# ---------------------------------------------------------------------------

TARGETS = {"version": "test", "rows": [
    {"endpoint": "A2B", "metric": [["a2b", "all", "mean"], ["a2b", "all", "p95"]],
     "bands": {"excellent": [0.25, 0.75], "good": [0.5, 1.5], "acceptable": [1.0, 2.2]}},
    {"endpoint": "BLACK", "kind": "black_depth", "synthetic_only": True,
     "bands": {"excellent": [0.5, 1.0], "good": [1.5, 2.0], "acceptable": [3.0, 3.5]}}]}


def _res(mean, p95, black_L, reach_L, kind="synthetic"):
    key = "a2b_heldout" if kind == "real" else "a2b"
    return {"datasets": [{"name": "X", "variant": "typical-targen900", "kind": kind,
                          "profiles": {"accurate": {"scores": {"argyll": {
                              key: {"all": {"mean": mean, "median": mean / 2, "p95": p95}},
                              "black": {"printed_L": black_L, "printed_ab": [0.3, 0.4],
                                        "reachable_L": {"darkest_neutral_L": reach_L}}}}}}}]}


def test_bands_test_the_mean_not_the_median():
    from benchmarks.research import targets
    rows = targets.band_run(_res(0.6, 1.0, 7.0, 7.0), TARGETS)
    assert rows[0]["band"] == "acceptable"          # median 0.3 would have read "good"


def test_the_black_band_is_judged_against_the_truths_reachable_black():
    from benchmarks.research import targets
    rows = targets.band_run(_res(0.2, 0.5, 21.8, 7.2), TARGETS)   # Agent 13's XKB case
    assert {r["endpoint"]: r["band"] for r in rows}["BLACK"] == "below"
    rows = targets.band_run(_res(0.2, 0.5, 7.4, 7.2), TARGETS)
    assert {r["endpoint"]: r["band"] for r in rows}["BLACK"] == "excellent"


def test_a_real_set_reads_its_held_out_a2b_and_skips_synthetic_only_rows():
    from benchmarks.research import targets
    rows = targets.band_run(_res(0.2, 0.5, 7.0, 7.0, kind="real"), TARGETS)
    assert [r["endpoint"] for r in rows] == ["A2B"] and rows[0]["band"] == "excellent"


@pytest.mark.skipif(not ARGYLL.exists(), reason="ArgyllCMS not installed")
def test_the_commercial_table_states_in_and_out_of_sample_and_gives_intervals(tmp_path):
    from benchmarks.research import commercial, datasets as dsm
    p = _smooth_profile(tmp_path)
    rng = np.random.default_rng(3)
    dev = rng.uniform(0, 0.6, (60, 4))
    lab = commercial.absolute_lab(p, dev, "argyll") + rng.normal(0, 0.3, (60, 3))
    ds = dsm.Dataset(name="R-test", kind="real", ti3=tmp_path / "x.ti3", n_channels=4,
                     color_rep="CMYK_XYZ", ink_limit=300.0, holdout_device=dev,
                     holdout_xyz=colour.lab_to_xyz(lab))
    r = commercial.compare_one(ds, {"ours": p}, (p, "reference", "argyll"), n_boot=200)
    assert "IN-SAMPLE" in r["reference_sample"] and "OUT-OF-SAMPLE" in r["ours_sample"]
    d = r["ours"]["ours"]["diff_vs_reference"]
    assert set(d) == {"median", "mean", "p95"}
    assert d["mean"]["ours_minus_reference"] == pytest.approx(0.0, abs=1e-9)
    assert d["mean"]["ci95"][0] <= 0.0 <= d["mean"]["ci95"][1]
    md = commercial.table([r])
    assert "in-sample" in md and "OUT-of-sample" in md and "95 % CI" in md


# ---------------------------------------------------------------------------
# D-17: the weighed adoption rule
# ---------------------------------------------------------------------------

def _decided(rows):
    from benchmarks.research import stats3
    return stats3.decide(rows, "colprof", "accurate", None)


def test_d17_adopts_big_wins_with_one_tiny_loss_but_strict_test_still_reports_it():
    from benchmarks.research import stats3
    wins = [_row(dataset=f"X{i}", diff=-0.3) for i in range(9)]
    loss = [_row(dataset="X9", endpoint="a2b.median", a=0.5, b=0.53, diff=0.03, rel=0.06,
                 ci95=[0.02, 0.04])]
    rows = _decided(wins + loss)
    for r in rows:                       # force the small loss past the minimum effect
        if r["dataset"] == "X9":
            r["verdict_per_printer_endpoint"] = "WORSE"
    assert not stats3.no_regression(rows)["pass"]           # the strict table still fails
    w = stats3.weighed_adoption(rows)
    assert w["pass"] and w["wins"] == 9 and w["losses"] == 1
    assert w["all_losses"][0]["small"]


def test_d17_blocks_a_loss_above_tolerance_a_safety_row_or_no_net_benefit():
    from benchmarks.research import stats3
    wins = [_row(dataset=f"X{i}", diff=-0.3) for i in range(9)]
    big = _decided(wins + [_row(dataset="X9", diff=0.3, b=1.3, ci95=[0.2, 0.4], rel=0.3)])
    assert not stats3.weighed_adoption(big)["pass"]
    grey = _decided(wins + [_row(dataset="X9", endpoint="neutral_de.median", diff=0.04,
                                 rel=0.05, a=0.8, b=0.84, ci95=[0.03, 0.05])])
    for r in grey:
        if r["dataset"] == "X9":
            r["verdict_per_printer_endpoint"] = "WORSE"
    w = stats3.weighed_adoption(grey)
    assert not w["pass"] and w["safety_losses"]
    few = _decided([_row(dataset="X0", diff=-0.3)] +
                   [_row(dataset="X9", endpoint="a2b.median", diff=0.03, rel=0.06, a=0.5,
                         b=0.53, ci95=[0.02, 0.04])])
    for r in few:
        if r["dataset"] == "X9":
            r["verdict_per_printer_endpoint"] = "WORSE"
    assert not stats3.weighed_adoption(few)["pass"]           # 1 win vs 1 loss: no net benefit
    assert not stats3.weighed_adoption(_decided(wins), safety=[{"row": "X3", "check": "black depth L*"}])["pass"]


def test_d17_safety_property_checks_have_zero_tolerance():
    from benchmarks.research import stats3

    def res(eng_scores):
        return {"datasets": [{"name": "X3", "variant": "typical-targen900", "profiles": {
            e: {"ok": True, "scores": {"argyll": s}} for e, s in eng_scores.items()}}]}
    base = {"black": {"printed_L": 7.0, "printed_ab": [0.2, 0.2]}, "white": {"max_ink_pct": 0.0},
            "b2a": {"over_limit_frac": 0.0}, "neutral": {"L_reversals": 0, "banding_max_d2": 0.3}}
    worse = json.loads(json.dumps(base))
    worse["black"]["printed_L"] = 9.0
    worse["white"]["max_ink_pct"] = 0.5
    s = stats3.safety_rows(res({"colprof": base, "accurate": worse}), None, "colprof", "accurate")
    assert {x["check"] for x in s} == {"black depth L*", "paper-white ink %"}
    assert stats3.safety_rows(res({"colprof": base, "accurate": base}), None, "colprof", "accurate") == []


# ---------------------------------------------------------------------------
# N: Agent 14's N-colour endpoints folded in (protocol v3 section N)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not ARGYLL.exists(), reason="ArgyllCMS not installed")
def test_ncolour_point_endpoints_are_index_aligned_and_in_stats3(tmp_path, printers):
    from benchmarks.research import ncpoints, stats3
    from workflow.profile_engine import icc_writer as icw
    n, g = 6, 4
    ax = np.linspace(0, 1, g)
    mesh = np.stack(np.meshgrid(*([ax] * n), indexing="ij"), -1).reshape(-1, n)
    lab = np.column_stack([100 - 80 * np.clip(mesh.sum(1) / 3, 0, 1),
                           30 * (mesh[:, 1] - mesh[:, 0]), 30 * (mesh[:, 2] - mesh[:, 4])])
    a2b = icw.make_mft2(n, 3, g, icw.lab_to_u16(lab))
    b2a = icw.make_mft2(3, n, 9, icw.device_to_u16(np.full((9 ** 3, n), 0.1)))
    p = icw.write_profile(tmp_path / "six.icc", icw.ProfileSpec(n_channels=n, description="x",
                                                                 color_rep="CMYKOG"),
                          {"A2B0": a2b, "A2B1": "A2B0", "A2B2": "A2B0",
                           "B2A0": b2a, "B2A1": "B2A0", "B2A2": "B2A0"})
    s1, s2 = {}, {}
    r = ncpoints.evaluate(p, printers["X5"], "argyll", s1)
    ncpoints.evaluate(p, printers["X5"], "argyll", s2)
    assert set(s1) == {"e7", "e7b", "e8", "e9"}
    assert all(s1[k].shape == s2[k].shape for k in s1)
    assert isinstance(r["gross_extrapolation"], int)
    eps = {f"{k}.{s}" for k, s in stats3.ENDPOINTS}
    assert {"e7.median", "e8.p95", "e9.median"} <= eps


def test_ncolour_safety_rows_have_zero_tolerance():
    from benchmarks.research import stats3
    base = {"black": {"printed_L": 7.0, "printed_ab": [0.2, 0.2]}, "nc": {"gross_extrapolation": 0}}
    worse = {"black": {"printed_L": 7.0, "printed_ab": [0.2, 0.2]}, "nc": {"gross_extrapolation": 3}}
    res = {"datasets": [{"name": "X5", "variant": "typical-ecg900", "profiles": {
        "fast": {"ok": True, "scores": {"argyll": base}, "ncq": {"NC5 visible jumps": 1}},
        "accurate": {"ok": True, "scores": {"argyll": worse}, "ncq": {"NC5 visible jumps": 4}}}}]}
    checks = {x["check"] for x in stats3.safety_rows(res, None, "fast", "accurate")}
    assert checks == {"F-12 gross extrapolation", "NC5 visible gradient jumps"}
