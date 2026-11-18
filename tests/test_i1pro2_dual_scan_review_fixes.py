"""The i1Pro 2 dual scan: the independent review of 2026-11-18 (REVIEW_446,
branch 1), each finding pinned by a test that failed on 3383b3907 and passes
after the fix. SYNTHETIC data only (the invented instrument of
tests/test_i1pro2_dual_scan_engine.py); the private recordings were used
only in the work folder (the accept / refuse table is in the spec).

MUST
* M1: a dual measurement continued with another factor, its source or white
  reference is refused before START (``start_guard`` -> ``mixed_factor``) and
  by the engine before anything is read; one file never holds two factors.
* M2: a dark strip's own UV pass is not refused: below a signal floor the
  pairing is SKIPPED (accepted with the note ``pairing_not_checked``); a
  black patch is not "values that are not numbers"; wrong pairings are still
  refused wherever the signal allows a judgment.
* M3: ``no_dual_calibration`` states the true cause.

SHOULD
* S1: a dual measurement continued as a single scan stops in the engine.
* S2: a calibration whose UV LED did not light is refused (``uv_tile_dark``),
  Python and C; a UV pass with no LED light has its own sentence.
* S3: the ruler-cut alignment measure refuses a UV pass that does not line up.
* S4: the refined factor's key is an HMAC with a per-install random secret.
* S5: the pass record keeps only what recomputing needs (Te, the UV pass in
  emission units), no white / tile / emission vectors.
* S6: texts fit their case; a refine file with swapped conditions says so.
* F8b (planted fault that survived): the i1Pro 3 arming step is never
  skipped because of ``--dual-scale``.

THE PERSON'S CHOICE (coordinator, 2026-11-18): the main file stays M0; the
Measure tab's M0 / M1 / M2 is recorded (``CHROMIQ_DUAL_CHOSEN``, the pass
record) and Build Profile is pre-set to it once every strip has both passes.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
sys.path.insert(0, str(Path(__file__).parent))
from replay_tools import HELPER, ReplaySession  # noqa: E402

import test_i1pro2_dual_scan_engine as T  # noqa: E402
from workflow.dual_scan import cut, model, pairing, record, scale, storage  # noqa: E402
from workflow.dual_scan.reasons import NOTES, REASONS, DualScanRefused  # noqa: E402
from workflow.dual_scan.scale import ScaleChoice  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
needs_helper = pytest.mark.skipif(not HELPER.exists(),
                                  reason="chromiq-chartread helper not built")
WL = model.WAVELENGTHS
BAND = (WL >= 410) & (WL <= 550)


def _measured(tmp_path, monkeypatch, s=1.137, extra=()):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, rp, truth, _ = T._chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    with ReplaySession(base, rp, extra_args=T._dual_args(cdir, s=s) + list(extra)) as ses:
        T._swipe(ses)
        T._done(ses, unread=True)
    return base, rp, truth, cdir, base.with_suffix(".ti3")


def _snapshot(main: Path, cdir: Path) -> dict:
    return {"main": main.read_bytes(),
            **{p.name: p.read_bytes() for p in sorted(cdir.iterdir())}}


# ===================================================================== M1

def test_m1_the_start_guard_refuses_another_factor_and_names_the_measurements_own(tmp_path):
    main = tmp_path / "m.ti3"
    main.write_text('CTI3\nKEYWORD "CHROMIQ_DUAL_SCAN"\nCHROMIQ_DUAL_SCAN "i1pro2"\n'
                    'KEYWORD "CHROMIQ_DUAL_SCALE"\nCHROMIQ_DUAL_SCALE "1.1370"\n'
                    'KEYWORD "CHROMIQ_DUAL_SCALE_SOURCE"\nCHROMIQ_DUAL_SCALE_SOURCE "standard"\n'
                    'KEYWORD "CHROMIQ_DUAL_WHITE"\nCHROMIQ_DUAL_WHITE "instrument"\n'
                    'BEGIN_DATA_FORMAT\nSAMPLE_ID\nEND_DATA_FORMAT\n'
                    'BEGIN_DATA\n1\nEND_DATA\n', encoding="latin-1")
    g = storage.start_guard
    assert g(main, True, ScaleChoice(1.137, "standard"), "instrument") is None
    assert g(main, True, ScaleChoice(1.25, "refined"), "instrument") == "mixed_factor"
    assert g(main, True, ScaleChoice(1.137, "refined"), "instrument") == "mixed_factor"
    assert g(main, True, ScaleChoice(1.137, "standard"), "table") == "mixed_factor"
    assert g(main, False) == "mixed_scan_kind"
    assert storage.continuation_choice(main) == (ScaleChoice(1.137, "standard"), "instrument")
    assert "factor" in REASONS["mixed_factor"]


@needs_helper
def test_m1_the_engine_stops_a_resume_with_another_factor_before_reading(tmp_path, monkeypatch):
    """The reviewer's probe (test_probe_dual_resume.py::test_b2): session 1
    at 1.137 standard, resumed at 1.25 refined. Before the fix strip A kept
    1.137 values under a header saying 1.25 refined."""
    base, rp, _t, cdir, main = _measured(tmp_path, monkeypatch, s=1.137)
    before = _snapshot(main, cdir)
    with ReplaySession(base, rp, extra_args=["-r"] + T._dual_args(cdir, s=1.25, source="refined")) as ses:
        ev = ses.wait_event("error", timeout=15)
    assert ev == {"event": "error", "kind": "mixed_factor", "detail": ""}
    assert not [e for e in ses.events if e.get("event") in ("strip_ready", "conditions")]
    assert _snapshot(main, cdir) == before                 # nothing written


@needs_helper
def test_m1_a_resume_with_the_same_factor_but_another_white_is_refused_too(tmp_path, monkeypatch):
    base, rp, _t, cdir, main = _measured(tmp_path, monkeypatch, s=1.137)
    with ReplaySession(base, rp, extra_args=["-r"] + T._dual_args(cdir, s=1.137, white="table")) as ses:
        ev = ses.wait_event("error", timeout=15)
    assert ev["kind"] == "mixed_factor"


def test_m1_averaging_dual_reads_of_two_factors_keeps_no_m1_m2(tmp_path):
    def f(name, scale_, source):
        p = tmp_path / name
        p.write_text('CTI3\nKEYWORD "CHROMIQ_DUAL_SCAN"\nCHROMIQ_DUAL_SCAN "i1pro2"\n'
                     f'KEYWORD "CHROMIQ_DUAL_SCALE"\nCHROMIQ_DUAL_SCALE "{scale_}"\n'
                     f'KEYWORD "CHROMIQ_DUAL_SCALE_SOURCE"\nCHROMIQ_DUAL_SCALE_SOURCE "{source}"\n'
                     'KEYWORD "CHROMIQ_DUAL_WHITE"\nCHROMIQ_DUAL_WHITE "instrument"\n'
                     'BEGIN_DATA_FORMAT\nSAMPLE_ID\nEND_DATA_FORMAT\nBEGIN_DATA\n1\nEND_DATA\n',
                     encoding="latin-1")
        return p
    a, b, c = f("a.ti3", "1.1560", "standard"), f("b.ti3", "1.1560", "standard"), f("c.ti3", "1.2000", "refined")
    plain = tmp_path / "p.ti3"
    plain.write_text("CTI3\nBEGIN_DATA_FORMAT\nSAMPLE_ID\nEND_DATA_FORMAT\nBEGIN_DATA\n1\nEND_DATA\n", encoding="utf-8")
    assert storage.average_guard([a, b]) is None
    assert storage.average_guard([a, c]) == "mixed_factor"
    assert storage.average_guard([a, plain]) == "mixed_scan_kind"
    assert storage.average_guard([plain, plain]) is None
    from workflow import i1pro3_conditions as ic
    assert ic.average_conditions(a, [a, c]) == {"M1": "average", "M2": "average"}


# ===================================================================== S1

@needs_helper
def test_s1_a_dual_measurement_continued_as_a_single_scan_stops(tmp_path, monkeypatch):
    """The reviewer's probe test_a_dual_then_single: before the fix the main
    file was rewritten WITHOUT the dual keyword and the strips of a dual and
    a single calibration looked like one ordinary single scan."""
    base, rp, _t, cdir, main = _measured(tmp_path, monkeypatch)
    before = _snapshot(main, cdir)
    with ReplaySession(base, rp, extra_args=["-r", "-S"]) as ses:
        ev = ses.wait_event("error", timeout=15)
    assert ev == {"event": "error", "kind": "mixed_scan_kind", "detail": ""}
    assert _snapshot(main, cdir) == before
    assert storage.read_dual_record(main).dual


# ===================================================================== M2

def _inst():
    return T._invented()


def _noisy_strip(levels, seed, cal, *, own=True):
    """A strip whose 380-400 nm ratio noise follows the level as MEASURED on
    instrument 1 (|ratio - 1| median 0.107 below 0.02, 0.072 at 0.02-0.05,
    0.036 at 0.05-0.1, 0.025 above)."""
    rng = np.random.default_rng(seed)
    lv = np.asarray(levels, float)
    L = lv[:, None] * (0.95 + 0.1 * rng.random((lv.size, 36)))
    sig = np.where(lv < 0.02, 0.16, np.where(lv < 0.05, 0.11, np.where(lv < 0.1, 0.05, 0.035)))
    tw = cal.uv_tile / cal.white
    U = L * tw[None, :] * (1.0 + sig[:, None] * rng.standard_normal((lv.size, 1)))
    return L, U


def test_m2_a_dark_strips_own_uv_pass_is_accepted_with_a_note():
    _tab, cal = _inst()
    for seed in range(20):
        L, U = _noisy_strip(np.linspace(0.012, 0.045, 12), seed, cal)
        ev = pairing.check_pairing(L, U, cal)
        assert ev.checked is False and ev.usable < pairing.MIN_USABLE
    assert "too dark" in NOTES["pairing_not_checked"]


def test_m2_a_black_patch_is_not_values_that_are_not_numbers():
    _tab, cal = _inst()
    tw = cal.uv_tile / cal.white
    L = np.vstack([np.zeros(36), np.full((4, 36), 0.5)])
    U = np.vstack([np.zeros(36), 0.5 * np.tile(tw, (4, 1))])
    assert pairing.check_pairing(L, U, cal).checked
    L[0] = -0.001                         # noise below zero
    assert pairing.check_pairing(L, U, cal).checked
    L[1:] = 0.01                          # all black
    U[1:] = 0.01 * tw
    assert not pairing.check_pairing(L, U, cal).checked


def test_m2_wrong_pairings_are_still_refused_wherever_the_signal_allows_it():
    _tab, cal = _inst()
    refused = 0
    for seed in range(20):
        La, Ua = _noisy_strip(np.random.default_rng(seed).uniform(0.06, 0.9, 15), seed, cal)
        Lb, Ub = _noisy_strip(np.random.default_rng(seed + 100).uniform(0.06, 0.9, 15), seed + 100, cal)
        assert pairing.check_pairing(La, Ua, cal).checked
        for L, U in ((La, Ub), (Lb, Ua), (La, Ua[::-1])):
            with pytest.raises(DualScanRefused) as e:
                pairing.check_pairing(L, U, cal)
            assert e.value.reason == "uv_pass_wrong_strip"
            refused += 1
    assert refused == 60
    # a dark strip's lamp pass with a BRIGHT strip's UV pass: judged, refused
    Ld, _ = _noisy_strip(np.full(10, 0.02), 1, cal)
    _, Ub = _noisy_strip(np.full(10, 0.6), 2, cal)
    with pytest.raises(DualScanRefused) as e:
        pairing.check_pairing(Ld, Ub, cal)
    assert e.value.reason == "uv_pass_wrong_strip"
    # a bright strip's lamp pass with a dark strip's UV pass: no LED light back
    Lb, _ = _noisy_strip(np.full(10, 0.6), 3, cal)
    _, Ud = _noisy_strip(np.full(10, 0.02), 4, cal)
    with pytest.raises(DualScanRefused) as e:
        pairing.check_pairing(Lb, Ud, cal)
    assert e.value.reason == "uv_pass_no_uv_light"


def test_m2_the_record_keeps_a_dark_strips_pass_with_its_note():
    tab, cal = _inst()
    r = record.PassRecord(["A"])
    r.add_calibration("c1", cal)
    L, U = _noisy_strip(np.linspace(0.012, 0.045, 12), 5, cal)
    r.lamp_read("A", L, "c1")
    assert r.uv_read("A", U, "c1") == record.OK
    assert r.uv["A"].notes == ["pairing_not_checked"]
    assert r.complete()


# ===================================================================== M3

def test_m3_no_dual_calibration_states_the_true_cause():
    s = REASONS["no_dual_calibration"]
    assert "15 %" not in s and "too bright" not in s
    # the UI review of 2026-11-18 (M-3): the same id comes from a UV tile
    # reading that failed, so the sentence names both causes and no action
    assert "did not succeed" in s and "without the dual scan" in s
    assert "M0 is not affected" in s
    assert "UV light" in s
    assert "15 %" not in model.__doc__.split("WHAT IS REFUSED")[1].split("154")[0]


# ===================================================================== S2

def test_s2_a_calibration_whose_uv_led_did_not_light_is_refused():
    tab, cal = _inst()
    dark = model.DualCalibration(cal.white, cal.uv_tile * 0.001, cal.emis, 139, 139)
    with pytest.raises(DualScanRefused) as e:
        model.compute(np.full(36, 0.5), np.full(36, 0.006), dark, tab, 1.15)
    assert e.value.reason == "uv_tile_dark"
    neg = model.DualCalibration(cal.white, -cal.uv_tile, cal.emis)
    with pytest.raises(DualScanRefused) as e:
        neg.checked(36)
    assert e.value.reason == "uv_tile_dark"
    # the recorded instruments' Te (207, 292-295) pass with room
    assert model.MIN_UV_TILE_TE <= 0.5 * 207 + 1
    assert "did not seem to light" in REASONS["uv_tile_dark"]


@needs_helper
def test_s2_the_engine_refuses_m1_m2_from_a_dark_uv_tile(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, rp, _t, _ = T._chart(tmp_path)
    text = rp.read_text(encoding="utf-8").splitlines()
    tline = [i for i, ln in enumerate(text) if ln.startswith("T ")][0]
    vals = [float(v) * 0.001 for v in text[tline].split()[1:]]
    text[tline] = "T " + " ".join(f"{v:.10g}" for v in vals)
    rp.write_text("\n".join(text) + "\n", encoding="utf-8")
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    with ReplaySession(base, rp, extra_args=T._dual_args(cdir)) as ses:
        T._swipe(ses)
        T._done(ses, unread=True)
    ev = [e for e in ses.events if e.get("event") == "conditions"]
    assert ev[-1] == {"event": "conditions", "active": False, "why": "dual_uv_tile_dark"}
    assert list(cdir.iterdir()) == []


def test_s2_a_uv_pass_without_led_light_has_its_own_sentence():
    _tab, cal = _inst()
    L, _ = _noisy_strip(np.linspace(0.2, 0.8, 10), 7, cal)
    with pytest.raises(DualScanRefused) as e:
        pairing.check_pairing(L, np.full((10, 36), 1e-6), cal)
    assert e.value.reason == "uv_pass_no_uv_light"
    assert "did not light" in REASONS["uv_pass_no_uv_light"]


# ===================================================================== S3

def _cut_case(shift_half_pitch: bool, uniform: bool = False):
    lp = np.arange(120) * 7.0
    nu = 72
    up = (nu - 1 - np.arange(nu) + 0.5) * (70.0 / 6.0)
    under = np.minimum(((up + (35.0 if shift_half_pitch else 0.0)) // 70.0).astype(int), 11)
    k = np.arange(nu)[:, None]
    j = np.arange(36)[None, :]
    base = np.ones(nu)[:, None] * 2.0 if uniform else \
        (np.where(under % 2, 3.0, 1.0) + 0.5 * under)[:, None]
    ur = base + 0.01 * np.sin(k * 1.7 + j)
    return [(c * 10, 10) for c in range(12)], lp, up, ur


def test_s3_a_uv_pass_half_a_pitch_off_is_refused_and_an_aligned_one_is_not():
    cells, lp, up, ur = _cut_case(False)
    r = cut.cut_uv_pass(cells, lp, up, ur)
    assert r.aligned_checked and r.flatness < 1e-4
    cells, lp, up, ur = _cut_case(True)
    with pytest.raises(DualScanRefused) as e:
        cut.cut_uv_pass(cells, lp, up, ur)
    assert e.value.reason == "uv_pass_misaligned"
    assert "lifted" in REASONS["uv_pass_misaligned"]


def test_s3_a_strip_of_one_colour_is_not_judged_for_alignment():
    cells, lp, up, ur = _cut_case(True, uniform=True)
    r = cut.cut_uv_pass(cells, lp, up, ur)
    assert r.aligned_checked is False and r.flatness != r.flatness


def test_s3_the_c_alignment_measure_is_the_python_one(tmp_path_factory):
    from tests.test_i1pro3_lights_modes import _build_and_run
    out = _build_and_run(tmp_path_factory, "i1pro2_dual_maths_test")
    got = {ln.split()[0]: ln.split()[1] for ln in out.splitlines() if ln.startswith("flat")}
    for key, shift in (("flat", False), ("flat_half", True)):
        cells, lp, up, ur = _cut_case(shift)
        spans = [(lp[a], lp[a + n - 1]) for a, n in cells]
        want = cut._flatness(spans, up, ur, cut.TRIM)
        assert float(got[key]) == pytest.approx(want, rel=1e-9, abs=1e-15)
    assert float(got["flat_half"]) > cut.MAX_FLATNESS > float(got["flat"])


# ===================================================================== S4

class _Store(dict):
    def set(self, k, v):
        self[k] = v


def test_s4_the_instrument_key_uses_a_random_secret_per_installation():
    a, b = _Store(), _Store()
    ka = storage.instrument_key("i1Pro 2", "1234567", a)
    kb = storage.instrument_key("i1Pro 2", "1234567", b)
    assert ka != kb                                   # not correlatable across installs
    assert ka == storage.instrument_key("i1Pro 2", "1234567", a)   # stable on one
    assert len(a[storage.KEY_SECRET_SETTING]) == 64
    # step 1's unsalted key (reversible from the serial in seconds) is gone
    old = hashlib.sha256(b"chromiq-dual-scan|i1pro 2|1234567").hexdigest()[:20]
    assert ka != old
    # the key is not any function of the serial alone: brute force over a
    # range of serials without the secret finds nothing
    hits = [s for s in range(1234500, 1234600)
            if hashlib.sha256(f"i1pro 2|{s}".encode()).hexdigest()[:20] == ka]
    assert hits == []
    a[storage.KEY_SECRET_SETTING] = "nonsense"
    assert storage.instrument_key("i1Pro 2", "1234567", a) != ka   # a new secret
    src = (ROOT / "workflow" / "dual_scan" / "storage.py").read_text(encoding="utf-8")
    assert "one-way key" not in src


# ===================================================================== S5

def test_s5_the_pass_record_keeps_only_what_recomputing_needs(tmp_path):
    tab, cal = _inst()
    r = record.PassRecord(["A"])
    r.add_calibration("c1", cal)
    L, U = _noisy_strip(np.random.default_rng(1).uniform(0.1, 0.9, 10), 1, cal)
    # give the strip some glow so the comparison means something
    m2 = L.copy()
    g = m2.mean(axis=1, keepdims=True) * 900.0 * np.exp(-0.5 * ((WL - 440) / 25.0) ** 2)
    L, U, _ = model.forward(m2, g, cal, tab, 1.15)
    r.lamp_read("A", L, "c1")
    assert r.uv_read("A", U, "c1") == record.OK
    p = tmp_path / "x.passes.json"
    r.save(p)
    d = json.loads(p.read_text(encoding="utf-8"))
    for c in d["calibrations"].values():
        assert set(c) == {"te", "lamp_clocks", "uv_clocks"} and len(c["te"]) == 18
    text = p.read_text(encoding="utf-8")
    for word in ("white", "uv_tile", "emis", "serial"):
        assert f'"{word}"' not in text
    assert all(len(row) == 18 for row in d["uv"]["A"]["data"])
    want = model.compute(L, U, cal, tab, 1.15)
    for rec in (r, record.PassRecord.load(p)):
        got = rec.strip_conditions("A", tab, 1.15)
        np.testing.assert_allclose(got.m2, want.m2, rtol=0, atol=1e-12)
        np.testing.assert_allclose(got.m1, want.m1, rtol=0, atol=1e-12)


def test_s5_a_uv_pass_needs_this_sittings_calibration(tmp_path):
    tab, cal = _inst()
    r = record.PassRecord(["A"])
    r.add_calibration("c1", cal)
    L, U = _noisy_strip(np.full(5, 0.5), 1, cal)
    r.lamp_read("A", L, "c1")
    p = tmp_path / "x.passes.json"
    r.save(p)
    q = record.PassRecord.load(p)
    assert q.uv_read("A", U, "c1") == record.FAILED          # c1's full values are gone
    assert q.uv["A"].reason == "no_dual_calibration"
    q.add_calibration("c2", cal)
    assert q.uv_read("A", U, "c2") == record.OK


# ===================================================================== S6

def test_s6_reason_sentences_fit_their_case():
    assert "second pass" in REASONS["uv_pass_count"]
    assert "Read the strip again" not in REASONS["uv_pass_count"]
    assert "second pass" in REASONS["uv_pass_missing"]
    for rid, text in {**REASONS, **NOTES}.items():
        assert "—" not in text, rid


def test_s6_a_refine_file_with_m1_and_m2_swapped_says_so():
    tab, cal = _inst()
    rng = np.random.default_rng(3)
    m2 = np.clip(rng.uniform(0.1, 0.9, (12, 1)) * np.ones((1, 36)), 0.02, 0.95)
    g = m2.mean(axis=1, keepdims=True) * 900.0 * np.exp(-0.5 * ((WL - 440) / 25.0) ** 2)
    L, U, M1 = model.forward(m2, g, cal, tab, 1.12)
    good = {"M0": L, "M1": M1, "M2": m2}
    assert scale.refine_scale(L, U, cal, tab, good)[0].value == pytest.approx(1.12, abs=2e-3)
    swapped = {"M0": L, "M1": m2, "M2": M1}
    with pytest.raises(DualScanRefused) as e:
        scale.refine_scale(L, U, cal, tab, swapped)
    assert e.value.reason == "refine_conditions_swapped"


def test_s6_the_spec_says_what_the_review_asked():
    spec = (ROOT / "docs" / "design" / "i1pro2_dual_scan.md").read_text(encoding="utf-8")
    assert "not yet measured" in spec                      # papers without brightener
    assert "0.1 to 0.25" in spec and "up to about 0.5" in spec
    assert "1.1547" in spec and "geometric mean" in spec
    assert "**Confirmed by:** Sebastian, 2026-11-18" in spec
    assert "one-way key" not in spec
    assert "provisional" in spec.lower()
    src = (ROOT / "workflow" / "dual_scan" / "scale.py").read_text(encoding="utf-8")
    assert "geometric mean" in src and "1.1547" in src


# ===================================================================== F8b

def test_f8b_the_i1pro3_arming_step_never_depends_on_the_dual_scale():
    """The planted fault that survived the review: the real i1Pro 3's arming
    skipped whenever --dual-scale was given. No replay can see it (the replay
    never arms), so the guard line is pinned: it may name the session's own
    dual state (cq_cond_dual, set only for an i1Pro 2) and never the
    request (cq_dual_req)."""
    src = (ROOT / "native" / "chartread_helper" / "chromiq_chartread.c").read_text(
        encoding="utf-8", errors="replace")
    body = src[src.index("static void cq_cond_arm(int on) {"):]
    body = body[:body.index("\n}\n")]
    assert "i1pro3_cq_cond_arm(cq_cond_it, on);" in body
    assert "cq_dual_req" not in body
    guard = re.search(r"if \((.*)\)\n\t\treturn;", body).group(1)
    assert guard == "!cq_cond_active || cq_cond_replay || cq_cond_dual || cq_cond_it == NULL"
    # cq_cond_dual is set only inside the i1Pro 2 branch
    fs = src[src.index("static void cq_cond_for_session("):]
    fs = fs[:fs.index("\n}\n")]
    branch = fs[fs.index("else if (cq_dual_req && it->dtype == instI1Pro2) {"):]
    sets = [m.start() for m in re.finditer(r"cq_cond_dual = 1;", fs)]
    assert len(sets) == 1 and fs.index(branch) < sets[0] < fs.index(branch) + 1200


# ===================================================================== the choice

def test_the_choice_is_passed_and_validated():
    c = ScaleChoice.standard()
    assert storage.helper_args(c, chosen="m1")[-2:] == ["--dual-chosen", "M1"]
    with pytest.raises(ValueError):
        storage.helper_args(c, chosen="D65")
    r = record.PassRecord(["A"])
    assert r.chosen == "M0"
    r.choose("M2")
    assert record.PassRecord.from_json(r.to_json()).chosen == "M2"
    with pytest.raises(ValueError):
        r.choose("polariser")


@needs_helper
def test_the_choice_is_recorded_the_main_stays_m0_and_build_profile_waits(tmp_path, monkeypatch):
    base, rp, truth, cdir, main = _measured(tmp_path, monkeypatch, extra=["--dual-chosen", "M1"])
    from workflow import i1pro3_conditions as ic
    from core.file_manager import Run
    h = T._check(base, cdir, truth)                       # main is M0, files as always
    for f in (main, cdir / f"{h}-M1.ti3", cdir / f"{h}-M2.ti3"):
        assert storage.read_dual_record(f).chosen == "M1", f
    assert ic.file_condition(main) == "M0"
    # a pass record with strip B's UV pass still due: M0, with the reason
    tab, cal = _inst()
    strips = sorted(truth)                                 # every strip of the chart
    assert len(strips) >= 2
    rec = record.PassRecord(strips)
    rec.choose("M1")
    rec.add_calibration("c1", cal)
    for s_ in strips:
        rec.lamp_read(s_, truth[s_][0], "c1")
    rec.uv_read(strips[0], model.forward(truth[strips[0]][2], np.zeros((len(truth[strips[0]][0]), 36)),
                                         cal, tab, 1.137)[1], "c1")
    rec.save(Run.dual_pass_record(main))
    cond, why = storage.build_from_preset(main)
    assert cond == "M0" and "second pass" in why and strips[1] in why
    assert storage.strips_without_second_pass(main) == strips[1:]
    # every strip with both passes: Build Profile starts from the choice
    for s_ in strips[1:]:
        rec.uv_read(s_, model.forward(truth[s_][2], np.zeros((len(truth[s_][0]), 36)),
                                      cal, tab, 1.137)[1], "c1")
    rec.save(Run.dual_pass_record(main))
    assert storage.build_from_preset(main) == ("M1", "")


def test_no_file_reason_names_the_dual_scan(tmp_path):
    from workflow import i1pro3_conditions as ic
    main = tmp_path / "m.ti3"
    main.write_text('CTI3\nKEYWORD "TARGET_INSTRUMENT"\nTARGET_INSTRUMENT "X-Rite i1Pro 2"\n'
                    'KEYWORD "CHROMIQ_DUAL_SCAN"\nCHROMIQ_DUAL_SCAN "i1pro2"\n'
                    'BEGIN_DATA_FORMAT\nSAMPLE_ID\nEND_DATA_FORMAT\nBEGIN_DATA\n1\nEND_DATA\n',
                    encoding="latin-1")
    why = ic.no_file_reason(main)
    assert "Only an X-Rite i1Pro 3" not in why and "dual scan" in why
