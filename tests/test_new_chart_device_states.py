"""New-chart dialog three-state device model (#72 Tier B).

State 1 (RGB) identity is locked by test_gen_state1_identity.py; this file
covers states 2/3 and the transitions: row visibility, source-mode gating,
ink-set derivation, inline profile validation, persistence round-trip and the
_on_ok threading into ChartSpec + targen args.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication  # noqa: E402

import ui.dialogs.ti2_relayout_dialog as M  # noqa: E402
from ui.dialogs.ti2_relayout_dialog import _NewChartDialog  # noqa: E402

GENERIC_CMYK = Path("/System/Library/ColorSync/Profiles/Generic CMYK Profile.icc")
needs_cmyk_profile = pytest.mark.skipif(
    not GENERIC_CMYK.exists(), reason="Generic CMYK profile not installed")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _FakeSettings:
    def __init__(self):
        self.d = {}

    def get(self, k, default=None):
        return self.d.get(k, default)

    def set(self, k, v):
        self.d[k] = v


@pytest.fixture
def dlg(qapp, tmp_path):
    d = _NewChartDialog(tmp_path, _FakeSettings())
    yield d
    d.deleteLater()


def _pick_device(d, data: str) -> None:
    d._device_type.setCurrentIndex(d._device_type.findData(data))


def test_ink_limit_tooltip_follows_the_row(dlg):
    """The ink-limit ⓘ sits in the grid's shared icon column, not inside the
    row, so it must hide with the row for Print RGB — where ink limit doesn't
    apply (regression: the ⓘ used to stay visible on RGB)."""
    assert dlg._nch_state() == 1                  # default: Print RGB
    assert dlg._nch_limit_row.isHidden()
    assert dlg._limit_tip.isHidden()              # ⓘ hidden too, not orphaned
    _pick_device(dlg, "cmyk")
    assert not dlg._nch_limit_row.isHidden()
    assert not dlg._limit_tip.isHidden()
    _pick_device(dlg, "rgb")
    assert dlg._nch_limit_row.isHidden()
    assert dlg._limit_tip.isHidden()


def test_state2_reveals_rows_and_gates_modes(dlg):
    assert dlg._nch_state() == 1
    assert dlg._nch_limit_row.isHidden() and dlg._nch_prof_row.isHidden()
    _pick_device(dlg, "cmyk")
    assert dlg._nch_state() == 2
    assert not dlg._nch_limit_row.isHidden()
    assert not dlg._nch_prof_row.isHidden()
    assert dlg._nch_inks_row.isHidden()          # plain CMYK: no extra slots
    # Paste is hex/RGB-only; generate works via the multi-ink rows (Tier C).
    assert not dlg._mode_paste.isEnabled()
    assert dlg._mode_generate.isEnabled()
    assert dlg._ink_limit.value() == 300         # the safe default
    # Row gating: RGB-cube constructs off, look-based off (no profile),
    # N-native rows + the multi-ink rows on. (Generate mode first — the whole
    # panel is greyed in seed mode, which would mask the per-row state.)
    dlg._mode_generate.setChecked(True)
    dlg._update_gen_counts()
    assert not dlg._gen_cube.isEnabled() and not dlg._gen_edges.isEnabled()
    assert not dlg._gen_skin.isEnabled() and not dlg._gen_blues.isEnabled()
    assert dlg._gen_neutral.isEnabled() and dlg._gen_nearneutral.isEnabled()
    assert dlg._gen_whiteblack.isEnabled()
    assert not dlg._nch_targen.isHidden()          # multi-ink rows revealed
    assert not dlg._nch_perink.isHidden() and not dlg._nch_pairs.isHidden()
    # Inactive rows keep their count visible but struck through (Basti's
    # visual hint): a disabled cube row's count is struck, an active
    # multi-ink row's is not.
    assert dlg._gen_cube_count.font().strikeOut()
    assert not dlg._nch_targen_count.font().strikeOut()
    dlg._nch_targen.setChecked(False)
    dlg._update_gen_counts()
    assert dlg._nch_targen_count.font().strikeOut()
    dlg._nch_targen.setChecked(True)
    assert "grey balance" in dlg._gen_nearneutral.toolTip()


def test_extra_ink_chips_and_ink_set_label(dlg):
    _pick_device(dlg, "cmykplus")
    assert not dlg._nch_inks_row.isHidden()
    dlg._on_add_ink(dlg._nch_add_ink.findData("g"))
    dlg._on_add_ink(dlg._nch_add_ink.findData("o"))
    assert dlg._extra_inks == ["g", "o"]       # the chips keep the click order
    # ... but the generators get the inks in Argyll's canonical order, the
    # order of the chart's own columns (agent 18 R5: an ink-specific set
    # would otherwise write into the wrong column).
    assert dlg._nch_ink_codes() == ["c", "m", "y", "k", "o", "g"]
    # Label shows the canonical targen order (CMYKOG), not the click order.
    assert "CMYKOG" in dlg._nch_inkset_lbl.text()
    dlg._remove_ink("g")
    assert dlg._extra_inks == ["o"]
    assert "CMYKO" in dlg._nch_inkset_lbl.text()


@needs_cmyk_profile
def test_profile_validation_match_and_mismatch(dlg):
    _pick_device(dlg, "cmyk")
    dlg._precond_path = str(GENERIC_CMYK)
    dlg._refresh_nch_state()
    assert dlg._nch_state() == 3
    assert dlg._nch_prof_status.text().startswith("✓")
    # Same profile on a 6-channel chart: channel mismatch, back to state 2.
    _pick_device(dlg, "cmykplus")
    dlg._on_add_ink(dlg._nch_add_ink.findData("o"))
    dlg._on_add_ink(dlg._nch_add_ink.findData("g"))
    assert dlg._nch_state() == 2
    assert dlg._nch_prof_status.text().startswith("✗")


def test_garbage_profile_is_rejected_inline(dlg, tmp_path):
    bad = tmp_path / "not_a_profile.icc"
    bad.write_bytes(b"garbage")
    _pick_device(dlg, "cmyk")
    dlg._precond_path = str(bad)
    dlg._refresh_nch_state()
    assert dlg._nch_state() == 2
    assert dlg._nch_prof_status.text().startswith("✗")


def test_device_state_persists_and_round_trips(dlg, qapp, tmp_path):
    _pick_device(dlg, "cmykplus")
    dlg._on_add_ink(dlg._nch_add_ink.findData("o"))
    dlg._ink_limit.setValue(280)
    # The device-gated generator rows persist too (Basti's report — the
    # generator-requirements checklist applies to the new rows).
    dlg._nch_targen.setChecked(False)
    dlg._nch_targen_n.setValue(1200)
    dlg._nch_perink_n.setValue(12)
    dlg._nch_pairs.setChecked(False)
    st = dlg._collect_gen_state()
    assert st["device"]["type"] == "cmykplus"
    assert st["device"]["extra_inks"] == ["o"]
    assert st["device"]["ink_limit"] == 280
    assert st["device"]["gen"] == {"targen": False, "targen_n": 1200,
                                   "perink": True, "perink_n": 12,
                                   "pairs": False, "pairs_n": 4,
                                   "triples": False, "triples_n": 2,
                                   "richblack": False, "richblack_n": 6,
                                   "richblack_k": 3,
                                   # agent 18 (D-16), off by default
                                   "perink_light": False, "pairs_grid": False,
                                   "fill_sparse": False}
    fresh = _NewChartDialog(tmp_path, _FakeSettings())
    fresh._apply_gen_state(st)
    assert fresh._device_type.currentData() == "cmykplus"
    assert fresh._extra_inks == ["o"]
    assert fresh._ink_limit.value() == 280
    assert not fresh._nch_targen.isChecked()
    assert fresh._nch_targen_n.value() == 1200
    assert fresh._nch_perink_n.value() == 12
    assert not fresh._nch_pairs.isChecked()
    # A pre-#72 state (no device key at all) resets the rows to factory —
    # the checklist's default-when-absent rule.
    fresh._apply_gen_state({"mode": "seed"})
    assert fresh._nch_targen.isChecked() and fresh._nch_targen_n.value() == 800
    assert fresh._nch_perink_n.value() == 8 and fresh._nch_pairs_n.value() == 4
    fresh.deleteLater()


def test_restore_defaults_resets_device_rows(dlg):
    _pick_device(dlg, "cmyk")
    dlg._nch_targen_n.setValue(2000)
    dlg._nch_perink.setChecked(False)
    dlg._restore_factory_defaults()
    assert dlg._device_type.currentData() == "rgb"      # back to state 1
    assert dlg._nch_targen_n.value() == 800
    assert dlg._nch_perink.isChecked()


def test_full_cycle_returns_to_golden_rgb_state(dlg):
    import json
    golden = json.loads(
        (Path(__file__).parent / "golden" / "gen_state_rgb_default.json")
        .read_text(encoding="utf-8"))
    _pick_device(dlg, "cmyk")
    _pick_device(dlg, "cmykplus")
    dlg._on_add_ink(dlg._nch_add_ink.findData("v"))
    dlg._ink_limit.setValue(260)
    _pick_device(dlg, "rgb")
    st = dlg._collect_gen_state()
    assert "device" not in st                      # state 1 carries no new keys
    assert sorted(st.keys()) == sorted(golden.keys())
    assert dlg._mode_paste.isEnabled() and dlg._mode_generate.isEnabled()


def test_on_ok_threads_device_into_spec_and_targen(dlg, monkeypatch):
    calls = {}

    def fake_seed(bin_dir, n, *, device="2", grey_steps=0, good_mode=True,
                  extra_args=None):
        calls["device"] = device
        calls["extra_args"] = list(extra_args or [])
        return [(0.0, 0.0, 0.0, 0.0), (10.0, 20.0, 30.0, 40.0)]

    monkeypatch.setattr(M.R, "seed_from_targen", fake_seed)
    _pick_device(dlg, "cmykplus")
    dlg._on_add_ink(dlg._nch_add_ink.findData("o"))
    dlg._on_add_ink(dlg._nch_add_ink.findData("g"))
    dlg._ink_limit.setValue(280)
    dlg._mode_seed.setChecked(True)
    dlg._on_ok()
    assert calls["device"] == "4"
    assert "-D5" in calls["extra_args"] and "-D7" in calls["extra_args"]
    assert "-l280" in calls["extra_args"]
    assert "-c" not in calls["extra_args"]         # no profile set
    assert dlg.result_spec.color_rep == "CMYKOG"
    assert dlg.result_spec.ink_limit == 280.0
    assert dlg.result_recipe["device"]["type"] == "cmykplus"
    assert dlg.result_program == [(0.0, 0.0, 0.0, 0.0), (10.0, 20.0, 30.0, 40.0)]


@needs_cmyk_profile
def test_state3_unlocks_perceptual_rows(dlg):
    dlg._mode_generate.setChecked(True)
    _pick_device(dlg, "cmyk")
    dlg._precond_path = str(GENERIC_CMYK)
    dlg._refresh_nch_state()
    assert dlg._nch_state() == 3
    assert dlg._gen_skin.isEnabled() and dlg._gen_blues.isEnabled()
    assert not dlg._gen_cube.isEnabled()           # cube-bound stays off forever
    # Back to state 2: perceptual re-locks with the needs-profile tooltip.
    dlg._clear_precond()
    assert not dlg._gen_skin.isEnabled()
    assert "preconditioning profile" in dlg._gen_skin.toolTip()
    # And back to RGB: original tooltips restored.
    _pick_device(dlg, "rgb")
    assert dlg._gen_cube.isEnabled() and dlg._gen_skin.isEnabled()
    assert "preconditioning" not in dlg._gen_skin.toolTip()


def test_nch_program_builds_device_tuples(dlg, monkeypatch):
    # State 2, no targen (stubbed out): ramps + pairs + rings + white/black.
    monkeypatch.setattr(M.R, "seed_from_targen",
                        lambda *a, **k: [(1.0, 2.0, 3.0, 4.0)])
    _pick_device(dlg, "cmyk")
    dlg._mode_generate.setChecked(True)
    for n in dlg._GEN_CHECKS:
        getattr(dlg, f"_gen_{n}").setChecked(False)
    dlg._gen_nearneutral.setChecked(True)
    dlg._gen_nearneutral_n.setValue(8)
    dlg._gen_whiteblack.setChecked(True)
    dlg._gen_unique.setChecked(True)
    dlg._nch_targen.setChecked(True)
    dlg._nch_targen_n.setValue(50)
    dlg._nch_perink.setChecked(True)
    dlg._nch_perink_n.setValue(4)
    dlg._nch_pairs.setChecked(True)
    dlg._nch_pairs_n.setValue(2)
    prog = dlg._build_generated_program()
    assert prog and all(len(p) == 4 for p in prog)
    # targen stub (1) + per-ink 16 + pairs 12 + rings + white/black anchors.
    from workflow.patch_generators import near_neutrals_count
    rings = near_neutrals_count(8, 1)
    # White/black tops up to N of each — a ring patch that already sits on an
    # anchor cell counts toward it, hence >= …+1 not a fixed +2.
    assert len(prog) >= 1 + 16 + 12 + rings + 1
    # Ticked-but-disabled RGB rows contribute nothing.
    dlg._gen_cube.setChecked(True)
    assert len(dlg._build_generated_program()) == len(prog)
    # White/black anchors present: ink white = all-0, black = K-only.
    assert (0.0, 0.0, 0.0, 0.0) in prog
    assert (0.0, 0.0, 0.0, 100.0) in prog


def test_profile_buttons_stay_icon_sized(dlg):
    # The app-wide QPushButton QSS (min-width: 72px) must not widen these —
    # stylesheet minimums override setFixedWidth, so the per-widget override
    # has to hold (Basti's live review, twice).
    _pick_device(dlg, "cmyk")
    dlg.show()
    for btn in (dlg._nch_prof_browse, dlg._nch_prof_clear):
        assert btn.width() <= 34, f"{btn.toolTip()}: {btn.width()}px wide"
    dlg.close()


def test_cube_hidden_on_restored_multiink_state(qapp, tmp_path):
    # Basti's repro: create a CMYK patch set, reopen the dialog — the device
    # state is remembered, and the 3D preview must be hidden from the start
    # (the old isVisible() guard never fired before the window was shown).
    settings = _FakeSettings()
    first = _NewChartDialog(tmp_path, settings)
    _pick_device(first, "cmyk")
    settings.set("new_chart_gen", first._collect_gen_state())
    first.deleteLater()
    reopened = _NewChartDialog(tmp_path, settings)
    assert reopened._device_type.currentData() == "cmyk"   # remembered
    assert reopened._nch_cube_hidden is True
    assert reopened._cube_panel.isHidden()
    assert reopened._fold_btn.isHidden()
    # Switching back to RGB brings the preview affordance back.
    _pick_device(reopened, "rgb")
    assert reopened._nch_cube_hidden is False
    assert not reopened._fold_btn.isHidden()
    reopened.deleteLater()


def test_on_ok_rgb_unchanged(dlg, monkeypatch):
    calls = {}

    def fake_seed(bin_dir, n, *, device="2", grey_steps=0, good_mode=True,
                  extra_args=None):
        calls["device"] = device
        calls["extra_args"] = list(extra_args or [])
        return [(0.0, 0.0, 0.0)]

    monkeypatch.setattr(M.R, "seed_from_targen", fake_seed)
    dlg._mode_seed.setChecked(True)
    dlg._on_ok()
    assert calls["device"] == "2"
    assert calls["extra_args"] == []
    assert dlg.result_spec.color_rep == "iRGB"
    assert dlg.result_spec.ink_limit is None


# ---------------------------------------------------------------------------
# #123 follow-up: triples + rich black rows, build order, recentred rings
# ---------------------------------------------------------------------------

def test_new_nd_rows_default_off_and_visible_only_multiink(dlg):
    assert not dlg._nch_triples.isChecked()
    assert not dlg._nch_richblack.isChecked()
    assert dlg._nch_triples.isHidden()          # RGB state: hidden
    _pick_device(dlg, "cmyk")
    assert not dlg._nch_triples.isHidden()
    assert not dlg._nch_richblack.isHidden()


def test_new_nd_rows_persist_roundtrip(qapp, tmp_path):
    settings = _FakeSettings()
    first = _NewChartDialog(tmp_path, settings)
    _pick_device(first, "cmyk")
    first._nch_triples.setChecked(True)
    first._nch_triples_n.setValue(3)
    first._nch_richblack.setChecked(True)
    first._nch_richblack_n.setValue(8)
    first._nch_richblack_k.setValue(4)
    settings.set("new_chart_gen", first._collect_gen_state())
    first.deleteLater()
    reopened = _NewChartDialog(tmp_path, settings)
    assert reopened._nch_triples.isChecked()
    assert reopened._nch_triples_n.value() == 3
    assert reopened._nch_richblack.isChecked()
    assert reopened._nch_richblack_n.value() == 8
    assert reopened._nch_richblack_k.value() == 4
    reopened.deleteLater()
    # Absent keys (an old saved state) load the sets OFF.
    old_state = dict(settings.get("new_chart_gen"))
    old_state["device"] = dict(old_state["device"])
    gen = dict(old_state["device"]["gen"])
    for k in ("triples", "triples_n", "richblack", "richblack_n",
              "richblack_k"):
        gen.pop(k, None)
    old_state["device"]["gen"] = gen
    settings.set("new_chart_gen", old_state)
    legacy = _NewChartDialog(tmp_path, settings)
    assert not legacy._nch_triples.isChecked()
    assert not legacy._nch_richblack.isChecked()
    legacy.deleteLater()


def test_nd_build_includes_new_sets_inside_limit(dlg, monkeypatch):
    _pick_device(dlg, "cmyk")
    dlg._ink_limit.setValue(280)
    for cb in (dlg._nch_targen, dlg._nch_perink, dlg._nch_pairs):
        cb.setChecked(False)
    for name in ("neutral", "nearneutral", "whiteblack", "fill", "unique"):
        getattr(dlg, f"_gen_{name}").setChecked(False)
    dlg._nch_triples.setChecked(True)
    dlg._nch_triples_n.setValue(2)
    dlg._nch_richblack.setChecked(True)
    dlg._nch_richblack_n.setValue(3)
    dlg._nch_richblack_k.setValue(2)
    program = dlg._build_generated_program()
    from workflow import patch_generators_nd as ND
    assert len(program) == (ND.ink_triple_overprints_count(4, 2)
                            + ND.rich_black_ramp_count(3, 2))
    assert all(sum(p) <= 280.0 + 1e-9 for p in program)
    assert all(len(p) == 4 for p in program)


def test_nd_fill_respects_ink_limit_through_dialog(dlg):
    _pick_device(dlg, "cmyk")
    dlg._ink_limit.setValue(240)
    for cb in (dlg._nch_targen, dlg._nch_perink, dlg._nch_pairs,
               dlg._nch_triples, dlg._nch_richblack):
        cb.setChecked(False)
    for name in ("neutral", "nearneutral", "whiteblack", "unique"):
        getattr(dlg, f"_gen_{name}").setChecked(False)
    dlg._gen_fill.setChecked(True)
    dlg._gen_fill_to.setValue(80)
    program = dlg._build_generated_program()
    assert program and all(sum(p) <= 240.0 + 1e-6 for p in program)


def test_nd_rings_recentre_through_profile(dlg, monkeypatch):
    # State 3: the rings must run through the preconditioning profile —
    # stub the xicclu bridge and check the centres actually shift.
    _pick_device(dlg, "cmyk")
    for cb in (dlg._nch_targen, dlg._nch_perink, dlg._nch_pairs,
               dlg._nch_triples, dlg._nch_richblack):
        cb.setChecked(False)
    for name in ("neutral", "whiteblack", "fill", "unique"):
        getattr(dlg, f"_gen_{name}").setChecked(False)
    dlg._gen_nearneutral.setChecked(True)
    dlg._precond_path = "/fake/profile.icc"
    monkeypatch.setattr(dlg, "_nch_state", lambda: 3)

    def fake_bridge(rgb, profile, bin_dir, ink_limit=None, **kw):
        from workflow import patch_generators_nd as ND
        out = []
        for r in rgb:
            naive = ND._invert_rgb_to_cmy(tuple(r), 4, 1e9)
            out.append((naive[0] + 7.0, naive[1], naive[2], 0.0))
        return out, 0
    import workflow.xicclu_runner as XR
    monkeypatch.setattr(XR, "to_device_via_profile", fake_bridge)
    recentred = dlg._build_generated_program()
    monkeypatch.setattr(dlg, "_nch_state", lambda: 2)
    naive = dlg._build_generated_program()
    assert len(recentred) == len(naive)
    shifts = [r[0] - v[0] for r, v in zip(recentred, naive)
              if 10.0 < r[0] < 90.0]
    assert shifts and all(abs(s - 7.0) < 1e-6 for s in shifts)


def test_nd_build_order_matches_panel(dlg):
    # De-dup priority contract: look-based sets come BEFORE the grey sets
    # in the panel, so the build must extend them in that order too.
    import inspect
    src = inspect.getsource(type(dlg)._build_generated_program_nch)
    i_perc = src.index("_GEN_PERCEPTUAL")
    i_neutral = src.index("neutral_ramp_device")
    i_rings = src.index("near_neutrals_device")
    assert i_perc < i_neutral < i_rings


def test_checked_but_gated_rgb_rows_grey_their_spins(dlg):
    # Basti's screenshot: cube ticked on RGB, then switch to CMYK — the
    # cube row is state-gated off, and its size spin must grey with it.
    dlg._mode_generate.setChecked(True)     # activate the generator panel
    dlg._gen_cube.setChecked(True)
    dlg._update_gen_counts()
    assert dlg._gen_cube_n.isEnabled()
    _pick_device(dlg, "cmyk")
    assert dlg._gen_cube.isChecked()            # ticked state survives…
    assert not dlg._gen_cube.isEnabled()        # …but the row is gated
    assert not dlg._gen_cube_n.isEnabled()      # and the spin greys too
    _pick_device(dlg, "rgb")
    assert dlg._gen_cube_n.isEnabled()          # restored with the row
