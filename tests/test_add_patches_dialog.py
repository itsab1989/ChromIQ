"""Editor "Add…" dialog (#46): single colour or generated colour sets."""
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.dialogs.ti2_relayout_dialog import _AddPatchesDialog, _NewChartDialog  # noqa: E402


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


def test_default_is_single_colour_mode(qapp):
    dlg = _AddPatchesDialog(_FakeSettings())
    assert dlg._add_mode_single.isChecked()
    # The generate panel is disabled until "Generate colour sets" is picked.
    assert not dlg._gen_panel.isEnabled()


def test_single_colour_returns_one_patch(qapp):
    dlg = _AddPatchesDialog(_FakeSettings())
    dlg._single_rgb = (100.0, 0.0, 0.0)
    dlg._on_add()
    assert dlg.result_program == [(100.0, 0.0, 0.0)]


def test_generate_mode_returns_generated_program(qapp):
    dlg = _AddPatchesDialog(_FakeSettings())
    dlg._add_mode_gen.setChecked(True)
    dlg._refresh_add_mode()
    assert dlg._gen_panel.isEnabled()
    # Only the cube, 4 per axis -> 64 patches.
    for n in dlg._GEN_CHECKS:
        getattr(dlg, f"_gen_{n}").setChecked(False)
    dlg._gen_cube.setChecked(True)
    dlg._gen_cube_n.setValue(4)
    dlg._update_gen_counts()
    dlg._on_add()
    assert dlg.result_program is not None
    assert len(dlg.result_program) == 64


def test_neutral_ramp_alone_is_pure_greys(qapp):
    # The Neutral grey ramp on its own produces only pure greys (no tints).
    dlg = _AddPatchesDialog(_FakeSettings())
    dlg._add_mode_gen.setChecked(True)
    dlg._refresh_add_mode()
    for n in dlg._GEN_CHECKS:
        getattr(dlg, f"_gen_{n}").setChecked(False)
    dlg._gen_neutral.setChecked(True)
    dlg._gen_neutral_n.setValue(12)
    dlg._update_gen_counts()
    assert "12" in dlg._gen_neutral_count.text()
    dlg._on_add()
    assert dlg.result_program is not None
    assert len(dlg.result_program) == 12
    for r, g, b in dlg.result_program:
        assert r == g == b


def test_neutral_and_near_neutrals_split_reproduces_old_total(qapp):
    # ramp(16) + near-neutrals(16, rings 1) = 16 + 16·6 = 112, the old combined
    # near-neutral greys total; near-neutrals adds only the off-axis tints.
    dlg = _AddPatchesDialog(_FakeSettings())
    dlg._add_mode_gen.setChecked(True)
    dlg._refresh_add_mode()
    for n in dlg._GEN_CHECKS:
        getattr(dlg, f"_gen_{n}").setChecked(False)
    dlg._gen_unique.setChecked(False)
    dlg._gen_neutral.setChecked(True)
    dlg._gen_neutral_n.setValue(16)
    dlg._gen_nearneutral.setChecked(True)
    dlg._gen_nearneutral_n.setValue(16)
    dlg._gen_nearneutral_rings.setValue(1)
    dlg._update_gen_counts()
    assert "16" in dlg._gen_neutral_count.text()
    assert "96" in dlg._gen_nearneutral_count.text()       # 16·6
    assert dlg._gen_nearneutral_off.isEnabled()            # offset always live
    assert len(dlg._build_generated_program()) == 16 + 96


def test_generate_choices_persist_to_settings(qapp):
    s = _FakeSettings()
    dlg = _AddPatchesDialog(s)
    dlg._add_mode_gen.setChecked(True)
    for n in dlg._GEN_CHECKS:
        getattr(dlg, f"_gen_{n}").setChecked(False)
    dlg._gen_skin.setChecked(True)
    dlg._on_add()
    saved = s.get("new_chart_gen")
    assert isinstance(saved, dict)
    assert saved["cb"]["skin"] is True and saved["cb"]["cube"] is False
    # A second Add dialog restores those colour-set choices.
    dlg2 = _AddPatchesDialog(s)
    assert dlg2._gen_skin.isChecked() and not dlg2._gen_cube.isChecked()


def test_add_dialog_shares_newchart_gen_state_without_clobbering_chart(qapp):
    """Saving from the Add dialog must not wipe the New-chart dialog's saved
    instrument / paper / layout — only the colour-set sub-state is touched."""
    s = _FakeSettings()
    s.set("new_chart_gen", {"instr": "3p", "paper": "Letter",
                            "cb": {"cube": True}, "sp": {"cube_n": 8}})
    dlg = _AddPatchesDialog(s)
    dlg._add_mode_gen.setChecked(True)
    dlg._gen_cube.setChecked(True)
    dlg._on_add()
    saved = s.get("new_chart_gen")
    assert saved["instr"] == "3p" and saved["paper"] == "Letter"


def test_newchart_generate_program_unaffected_by_refactor(qapp, tmp_path):
    """Regression: the New-chart dialog still builds a program from its panel."""
    dlg = _NewChartDialog(tmp_path, _FakeSettings())
    dlg._mode_generate.setChecked(True)
    for n in dlg._GEN_CHECKS:
        getattr(dlg, f"_gen_{n}").setChecked(False)
    dlg._gen_cube.setChecked(True)
    dlg._gen_cube_n.setValue(3)
    dlg._update_gen_counts()
    assert len(dlg._build_generated_program()) == 27


def test_add_with_no_chart_open_seeds_a_chart_and_previews(qapp, monkeypatch):
    """#46 follow-up: adding patches with nothing loaded must seed a fresh
    chart (so a preview renders), not silently fill a grid with no spec."""
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QDialog
    import ui.dialogs.ti2_relayout_dialog as M

    settings = AppSettings()
    # IniFormat (not the native Windows registry) so clear() never hits
    # "key marked for deletion" registry warnings on Windows.
    settings._qs = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                             "chromiq-test", "add-patches")
    settings._qs.clear()
    editor = M.Ti2RelayoutDialog(ArgyllRunner(settings), settings)
    assert editor._spec is None

    # Stub the Add dialog to "return" two generated colours, and stub the
    # render so the test doesn't shell out to printtarg.
    class _StubAdd:
        def __init__(self, *a, **k):
            self.result_program = [(0.0, 0.0, 0.0), (100.0, 100.0, 100.0)]

        def exec(self):
            return QDialog.DialogCode.Accepted
    monkeypatch.setattr(M, "_AddPatchesDialog", _StubAdd)
    # THE PREVIEW HAS TWO RENDERERS, AND THIS USED TO WATCH ONLY ONE.
    #
    # `_set_chart` chooses between them: an engine chart previews through
    # `_do_engine_preview`, a printtarg chart through `_regenerate`. This test
    # watched `_regenerate` alone, which was safe only for as long as
    # `_engine_active()` was permanently False — and that WAS the defect
    # (B8-79: a widget's visibility standing in for "is this an engine chart",
    # nailed to False by `72c54d1f` for two months). With the predicate fixed,
    # a from-scratch chart follows the layout-engine setting, which is on by
    # default, so the engine draws it and `_regenerate` is correctly not
    # called. The question this test asks is "was a preview kicked off", so it
    # now watches both answers.
    rendered = []
    monkeypatch.setattr(editor, "_regenerate", lambda **k: rendered.append(k))
    monkeypatch.setattr(editor._engine_preview_timer, "start",
                        lambda *a: rendered.append("engine"))

    editor._add_patch()
    assert editor._spec is not None          # a chart was seeded
    assert editor._grid.count() == 2         # patches landed in the grid
    assert rendered, (                       # initial preview was kicked off
        "neither renderer was asked to draw the seeded chart "
        f"(engine active: {editor._engine_active()})")


def test_fill_counts_existing_chart_patches(qapp):
    """#51: in the Add dialog, "Fill remaining gaps: N" tops the *whole* chart
    up to N — patches already on the chart count, rather than adding N more."""
    existing = [(float(i % 100), 0.0, 0.0) for i in range(60)]
    dlg = _AddPatchesDialog(_FakeSettings(), existing_patches=existing)
    dlg._add_mode_gen.setChecked(True)
    dlg._refresh_add_mode()
    for n in dlg._GEN_CHECKS:
        getattr(dlg, f"_gen_{n}").setChecked(False)
    dlg._gen_fill.setChecked(True)
    dlg._gen_fill_to.setValue(100)
    dlg._update_gen_counts()
    assert len(dlg._build_generated_program()) == 40        # 60 there + 40 = 100


def test_generators_avoid_existing_patches(qapp):
    """#89: 'Ensure unique colours' must keep even the topmost generator clear of
    the chart's EXISTING patches, not just clear of the other generators."""
    from ui.dialogs.ti2_relayout_dialog import _GEN_MIN_DIST
    # Existing patches sitting exactly on the 4³ RGB-cube grid the generator
    # would otherwise place onto.
    grid = [0.0, 100.0 / 3, 200.0 / 3, 100.0]
    existing = [(r, g, b) for r in grid for g in grid for b in grid]
    dlg = _AddPatchesDialog(_FakeSettings(), existing_patches=existing)
    dlg._add_mode_gen.setChecked(True)
    dlg._refresh_add_mode()
    for n in dlg._GEN_CHECKS:
        getattr(dlg, f"_gen_{n}").setChecked(False)
    dlg._gen_cube.setChecked(True)
    dlg._gen_cube_n.setValue(4)
    dlg._gen_unique.setChecked(True)
    dlg._update_gen_counts()

    program = dlg._build_generated_program()
    assert program
    # Every generated patch must be at least the minimum distance from every
    # existing patch (it can't sit on top of one any more).
    for p in program:
        nearest = min((p[0] - e[0]) ** 2 + (p[1] - e[1]) ** 2 + (p[2] - e[2]) ** 2
                      for e in existing) ** 0.5
        assert nearest >= _GEN_MIN_DIST - 1e-6, f"{p} only {nearest:.2f} from an existing patch"


def test_fill_over_target_adds_nothing(qapp):
    existing = [(float(i % 100), 1.0, 2.0) for i in range(150)]
    dlg = _AddPatchesDialog(_FakeSettings(), existing_patches=existing)
    dlg._add_mode_gen.setChecked(True)
    dlg._refresh_add_mode()
    for n in dlg._GEN_CHECKS:
        getattr(dlg, f"_gen_{n}").setChecked(False)
    dlg._gen_fill.setChecked(True)
    dlg._gen_fill_to.setValue(100)              # already past it
    dlg._update_gen_counts()
    assert dlg._build_generated_program() == []


def test_fill_without_existing_chart_unchanged(qapp):
    """New-chart-style use (no existing patches) still fills to the target."""
    dlg = _AddPatchesDialog(_FakeSettings())    # existing_patches defaults to []
    dlg._add_mode_gen.setChecked(True)
    dlg._refresh_add_mode()
    for n in dlg._GEN_CHECKS:
        getattr(dlg, f"_gen_{n}").setChecked(False)
    dlg._gen_cube.setChecked(True)
    dlg._gen_cube_n.setValue(3)                 # 27
    dlg._gen_fill.setChecked(True)
    dlg._gen_fill_to.setValue(100)
    dlg._update_gen_counts()
    assert len(dlg._build_generated_program()) == 100


class _StubPanel:
    """Captures what the dialog pushes to the embedded cube panel."""
    def __init__(self):
        self.pushed = None
        self.torn_down = 0

    def set_program(self, program, existing_program=None):
        self.pushed = (list(program), list(existing_program or []))

    def teardown(self):
        self.torn_down += 1


def test_cube_panel_is_embedded(qapp):
    """Both dialogs build an always-present embedded cube panel."""
    assert _AddPatchesDialog(_FakeSettings())._cube_panel is not None


def test_cube_folded_by_default_and_toggles(qapp):
    """The cube starts folded away; the toggle reveals it and remembers it."""
    s = _FakeSettings()
    dlg = _AddPatchesDialog(s)
    assert dlg._cube_shown is False
    assert dlg._fold_btn.isChecked() is False
    dlg._fold_btn.setChecked(True)                    # user reveals the cube
    assert dlg._cube_shown is True
    assert s.get("new_chart_show_cube") is True       # remembered

    # A second dialog opens with the cube already shown.
    assert _AddPatchesDialog(s)._cube_shown is True


@pytest.mark.parametrize("show_cube", [False, True])
def test_exec_builds_cube_view_before_going_modal(qapp, monkeypatch, show_cube):
    """Regression (issue #38 / app freeze): the cube's QWebEngineView must be
    realized while the dialog is still non-modal — for BOTH a folded and an
    unfolded open. Creating its native surface inside the application-modal
    dialog wedges the modal grab and freezes the whole app on Windows. So
    exec() must call panel.ensure_view() before delegating to QDialog's modal
    loop; a folded open still pre-builds it (hidden) so a later unfold reuses
    the surface instead of spawning one while modal."""
    from PyQt6.QtWidgets import QApplication, QDialog

    s = _FakeSettings()
    s.set("new_chart_show_cube", show_cube)
    dlg = _AddPatchesDialog(s)

    order = []

    class _Panel:
        def __init__(self): self._v = show_cube
        def ensure_view(self): order.append("ensure_view")
        def isVisible(self): return self._v
        def setVisible(self, v): self._v = v
        def minimumWidth(self): return 360
        # No-op so a queued signal (e.g. a live-count refresh) firing on this
        # stub after the test — once another test spins an event loop — can't
        # crash with AttributeError; the real panel renders the program here.
        def set_program(self, *a, **k): pass
    dlg._cube_panel = _Panel()

    # Replace the real show / event pump / modal loop so the test neither opens
    # a window nor blocks; just record the call order.
    monkeypatch.setattr(dlg, "show", lambda: order.append("show"))
    monkeypatch.setattr(QApplication, "processEvents",
                        staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(
        QDialog, "exec",
        lambda self: order.append("modal") or QDialog.DialogCode.Rejected.value)

    dlg.exec()
    assert "ensure_view" in order, order
    assert order.index("ensure_view") < order.index("modal"), order


def test_live_preview_pushes_existing_plus_new(qapp):
    """In generate mode the panel gets the generated program *and* the chart's
    existing patches (the merged view from the Add flow)."""
    existing = [(0.0, 0.0, 0.0), (100.0, 100.0, 100.0)]
    dlg = _AddPatchesDialog(_FakeSettings(), existing_patches=existing)
    dlg._add_mode_gen.setChecked(True)
    dlg._refresh_add_mode()
    for n in dlg._GEN_CHECKS:
        getattr(dlg, f"_gen_{n}").setChecked(False)
    dlg._gen_cube.setChecked(True)
    dlg._gen_cube_n.setValue(3)                       # 27

    dlg._cube_panel = _StubPanel()
    dlg._cube_shown = True                            # preview unfolded
    dlg._do_push_live_preview()
    program, pushed_existing = dlg._cube_panel.pushed
    assert len(program) == 27
    assert pushed_existing == existing


def test_live_preview_follows_single_colour_mode(qapp):
    """In single-colour mode the cube previews the colour being added (not a
    stale generated view, and no longer empty) (#96)."""
    existing = [(10.0, 10.0, 10.0)]
    dlg = _AddPatchesDialog(_FakeSettings(), existing_patches=existing)
    dlg._add_mode_single.setChecked(True)             # not generating

    dlg._cube_panel = _StubPanel()
    dlg._cube_shown = True                            # preview unfolded
    dlg._do_push_live_preview()
    program, pushed_existing = dlg._cube_panel.pushed
    assert program == [dlg._single_rgb]               # the colour being added
    assert pushed_existing == existing


def test_done_tears_down_cube_panel(qapp):
    """Closing the dialog (any path) drains the embedded web view once."""
    dlg = _AddPatchesDialog(_FakeSettings())
    dlg._cube_panel = _StubPanel()
    dlg.reject()                                       # Cancel routes via done()
    assert dlg._cube_panel.torn_down == 1


def test_fill_counts_white_black_not_on_top(qapp):
    """Pure white & black must count toward the fill target, not stack on top:
    3 of each + fill-to-50 yields 50 total (with all 6 anchors present)."""
    dlg = _AddPatchesDialog(_FakeSettings())
    dlg._add_mode_gen.setChecked(True)
    dlg._refresh_add_mode()
    for n in dlg._GEN_CHECKS:
        getattr(dlg, f"_gen_{n}").setChecked(False)
    dlg._gen_whiteblack.setChecked(True)
    dlg._gen_whiteblack_n.setValue(3)            # 3 white + 3 black
    dlg._gen_fill.setChecked(True)
    dlg._gen_fill_to.setValue(50)
    dlg._update_gen_counts()
    prog = dlg._build_generated_program()
    assert len(prog) == 50                       # counted within, not 56
    anchors = sum(1 for p in prog
                  if tuple(p) in {(100.0, 100.0, 100.0), (0.0, 0.0, 0.0)})
    assert anchors == 6                          # the repeats are kept verbatim


def test_total_matches_built_program_with_foreign_existing(qapp):
    # #60: the Total is the patches the current set selection produces (the
    # additions: ticked sets + white/black + fill), NOT the existing chart. The
    # built program is used rather than the per-set estimate, so white/black
    # de-dup against the chart's existing patches (which came from elsewhere —
    # a preset's .ti1) doesn't drift (the original 921-vs-924).
    import re
    import workflow.patch_generators as G
    existing = G.rgb_cube(9)  # a "foreign" chart, not built by the recipe
    dlg = _AddPatchesDialog(_FakeSettings(), existing_patches=existing)
    dlg._add_mode_gen.setChecked(True)
    dlg._refresh_add_mode()
    for n in dlg._GEN_CHECKS:
        getattr(dlg, f"_gen_{n}").setChecked(False)
    dlg._gen_cube.setChecked(True)
    dlg._gen_whiteblack.setChecked(True)
    dlg._gen_fill.setChecked(True)
    dlg._gen_fill_to.setValue(900)
    dlg._update_gen_counts()
    dlg._do_push_live_preview()           # the debounced exact rebuild
    shown = int(re.search(r"(\d+)", dlg._gen_total.text()).group(1))
    assert shown == len(dlg._build_generated_program())   # additions only


def test_add_dialog_has_info_button_with_generator_help(qapp):
    # #66 follow-up (Knut): the Add window must carry an ⓘ, and its body must
    # include the same generator-sets help the New-chart dialog has.
    from ui.tooltip_button import TooltipButton
    from ui.dialogs.ti2_relayout_dialog import _GEN_SETS_HELP
    dlg = _AddPatchesDialog(_FakeSettings())
    tips = dlg.findChildren(TooltipButton)
    assert tips, "Add dialog has no ⓘ button"
    assert any(_GEN_SETS_HELP in t._body for t in tips), \
        "no ⓘ carries the generator-sets help"


def test_gen_sets_help_matches_new_chart_tooltip():
    # The New-chart ⓘ is BUILT from the shared constant — tr(intro) +
    # tr(_GEN_SETS_HELP) + tr(closing) — so the two ⓘ can't drift (#66,
    # restructured in #124). Assert all three parts are real catalog keys
    # the extractor sees, and that the help now covers every set row and
    # the multi-ink availability rules (#124 report 2).
    from scripts.i18n_extract import extract_keys
    from ui.dialogs.ti2_relayout_dialog import (_GEN_SETS_HELP,
                                                _NEW_CHART_TIP_CLOSING,
                                                _NEW_CHART_TIP_INTRO)
    keys = set(extract_keys())
    assert _GEN_SETS_HELP in keys
    assert _NEW_CHART_TIP_INTRO in keys
    assert _NEW_CHART_TIP_CLOSING in keys
    for needle in ("Gamut-corner emphasis", "Sunrises", "Flamingos",
                   "Colour extremes", "Pure white & black",
                   "Even coverage (targen)", "Per-ink ramps",
                   "Ink-pair overprints", "Ink-triple overprints",
                   "Rich-black ramp", "preconditioning profile",
                   "paper-white filler"):
        assert needle in _GEN_SETS_HELP, f"help lost its {needle!r} coverage"


def test_white_black_added_over_existing_chart(qapp):
    """#76: pure white & black are deliberate anchors — with each=2 they add
    2 white + 2 black even when the existing chart already holds white/black,
    instead of de-duping to 0."""
    existing = [(100.0, 100.0, 100.0), (100.0, 100.0, 100.0),
                (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (50.0, 50.0, 50.0)]
    dlg = _AddPatchesDialog(_FakeSettings(), existing_patches=existing)
    for cb in (dlg._gen_cube, dlg._gen_skin, dlg._gen_blues, dlg._gen_greens,
               dlg._gen_sunrises, dlg._gen_flamingos, dlg._gen_neutral,
               dlg._gen_nearneutral, dlg._gen_edges, dlg._gen_hs,
               dlg._gen_pastel, dlg._gen_image, dlg._gen_fill):
        cb.setChecked(False)
    dlg._gen_whiteblack.setChecked(True)
    dlg._gen_whiteblack_n.setValue(2)
    dlg._update_gen_counts()
    assert "4" in dlg._gen_whiteblack_count.text()
    prog = dlg._build_generated_program()
    assert prog.count((100.0, 100.0, 100.0)) == 2
    assert prog.count((0.0, 0.0, 0.0)) == 2


def test_flamingos_and_edges_between_in_program(qapp):
    """Flamingos is a real set in the program, and Saturated edges' 'between'
    control fills evenly relative to the cube's steps (Knut, #78)."""
    dlg = _AddPatchesDialog(_FakeSettings())
    dlg._add_mode_gen.setChecked(True)
    dlg._refresh_add_mode()
    for n in dlg._GEN_CHECKS:
        getattr(dlg, f"_gen_{n}").setChecked(False)
    dlg._gen_unique.setChecked(False)                  # isolate raw counts
    # cube 4 → 64; edges between=2 with cube_n=4 → 12·2·3 = 72; flamingos 10×1.
    dlg._gen_cube.setChecked(True)
    dlg._gen_cube_n.setValue(4)
    dlg._gen_edges.setChecked(True)
    dlg._gen_edges_n.setValue(2)
    dlg._gen_edges_faces.setValue(0)
    dlg._gen_flamingos.setChecked(True)
    dlg._gen_flamingos_n.setValue(10)
    dlg._gen_flamingos_layers.setValue(1)
    dlg._update_gen_counts()
    assert "72" in dlg._gen_edges_count.text()
    assert "10" in dlg._gen_flamingos_count.text()
    assert len(dlg._build_generated_program()) == 64 + 72 + 10

    # Edges keys to the cube: turn the cube off and it falls back to 2 steps
    # (one gap per edge) and now restores the 8 corner tips → 12·2·1 + 8 = 32.
    dlg._gen_cube.setChecked(False)
    dlg._update_gen_counts()
    assert "32" in dlg._gen_edges_count.text()


def test_flamingos_persists_and_restores_to_default(qapp):
    """New generator values save on commit and 'Restore defaults' brings them
    back (the persistence rule for every new set)."""
    dlg = _AddPatchesDialog(_FakeSettings())
    dlg._gen_flamingos.setChecked(False)
    dlg._gen_flamingos_n.setValue(33)
    st = dlg._collect_gen_sets()
    assert st["cb"]["flamingos"] is False
    assert st["sp"]["flamingos_n"] == 33
    # Restoring the factory baseline re-ticks it and resets the value.
    dlg._apply_gen_sets({"cb": dlg._GEN_FACTORY["cb"],
                         "sp": dlg._GEN_FACTORY["sp"]})
    assert dlg._gen_flamingos.isChecked() is True
    assert dlg._gen_flamingos_n.value() == 64


def test_corner_edges_in_program_and_persist(qapp):
    """Gamut-corner emphasis (edge patches): 24×edge patches (+ the 8 tips when
    nothing else supplies them), and its 'edge' value saves and restores."""
    dlg = _AddPatchesDialog(_FakeSettings())
    dlg._add_mode_gen.setChecked(True)
    dlg._refresh_add_mode()
    for n in dlg._GEN_CHECKS:
        getattr(dlg, f"_gen_{n}").setChecked(False)
    dlg._gen_unique.setChecked(False)
    dlg._gen_corners.setChecked(True)
    dlg._gen_corners_edge.setValue(2)      # 24 × 2 = 48 edge patches
    dlg._update_gen_counts()
    # Cube + edges both off → also restores the 8 tips: 48 + 8.
    assert "56" in dlg._gen_corners_count.text()
    assert len(dlg._build_generated_program()) == 56
    dlg._gen_cube.setChecked(True)         # cube supplies the tips now → 48
    dlg._update_gen_counts()
    assert "48" in dlg._gen_corners_count.text()

    st = dlg._collect_gen_sets()
    assert st["cb"]["corners"] is True and st["sp"]["corners_edge"] == 2
    dlg._apply_gen_sets({"cb": dlg._GEN_FACTORY["cb"],
                         "sp": dlg._GEN_FACTORY["sp"]})
    assert dlg._gen_corners.isChecked() is False
    assert dlg._gen_corners_edge.value() == 2


def test_colour_extremes_in_program_and_persist(qapp):
    """Colour extremes: 6×per_end spiral patches at the chromatic corners, with
    'per end'/'reach' saved and restored, and the tip-ownership chain."""
    dlg = _AddPatchesDialog(_FakeSettings())
    dlg._add_mode_gen.setChecked(True)
    dlg._refresh_add_mode()
    for n in dlg._GEN_CHECKS:
        getattr(dlg, f"_gen_{n}").setChecked(False)
    dlg._gen_unique.setChecked(False)
    dlg._gen_spirals.setChecked(True)
    dlg._gen_spirals_end.setValue(5)       # 6 × 5 = 30 spiral patches
    dlg._gen_spirals_reach.setValue(12)
    dlg._update_gen_counts()
    # Nothing else on → it owns the 6 colour tips: 30 + 6.
    assert "36" in dlg._gen_spirals_count.text()
    assert len(dlg._build_generated_program()) == 36
    # Gamut-corner emphasis ranks above it for the tips: enable it and the spiral
    # no longer adds them.
    dlg._gen_corners.setChecked(True)
    dlg._gen_corners_edge.setValue(1)
    dlg._update_gen_counts()
    assert "30" in dlg._gen_spirals_count.text()   # back to 6×5, no tips

    st = dlg._collect_gen_sets()
    assert st["cb"]["spirals"] is True
    assert st["sp"]["spirals_end"] == 5 and st["sp"]["spirals_reach"] == 12
    dlg._apply_gen_sets({"cb": dlg._GEN_FACTORY["cb"],
                         "sp": dlg._GEN_FACTORY["sp"]})
    assert dlg._gen_spirals.isChecked() is False
    assert dlg._gen_spirals_end.value() == 8 and dlg._gen_spirals_reach.value() == 16


def test_neutral_generators_persist_and_restore(qapp):
    """The two split generators save their state and 'Restore defaults' brings
    them back to the baseline derived from the old near-neutral greys."""
    dlg = _AddPatchesDialog(_FakeSettings())
    dlg._add_mode_gen.setChecked(True)
    dlg._refresh_add_mode()
    dlg._gen_neutral.setChecked(False)
    dlg._gen_neutral_n.setValue(24)
    dlg._gen_nearneutral.setChecked(True)
    dlg._gen_nearneutral_n.setValue(20)
    dlg._gen_nearneutral_rings.setValue(3)
    dlg._gen_nearneutral_off.setValue(6)
    st = dlg._collect_gen_sets()
    assert st["cb"]["neutral"] is False and st["cb"]["nearneutral"] is True
    assert st["sp"]["neutral_n"] == 24
    assert st["sp"]["nearneutral_n"] == 20
    assert st["sp"]["nearneutral_rings"] == 3 and st["sp"]["nearneutral_off"] == 6
    # Restore factory → both back on at the old-greys-derived defaults.
    dlg._apply_gen_sets({"cb": dlg._GEN_FACTORY["cb"],
                         "sp": dlg._GEN_FACTORY["sp"]})
    assert dlg._gen_neutral.isChecked() and dlg._gen_nearneutral.isChecked()
    assert dlg._gen_neutral_n.value() == 16
    assert dlg._gen_nearneutral_n.value() == 16
    assert dlg._gen_nearneutral_rings.value() == 1
    assert dlg._gen_nearneutral_off.value() == 4


def test_legacy_greys_state_migrates_to_split(qapp):
    """A pre-split saved state (combined 'greys' + 'greysmid') loads forward
    into the two new generators, preserving the user's settings and total."""
    dlg = _AddPatchesDialog(_FakeSettings())
    dlg._add_mode_gen.setChecked(True)
    dlg._refresh_add_mode()
    for n in dlg._GEN_CHECKS:
        getattr(dlg, f"_gen_{n}").setChecked(False)
    dlg._gen_unique.setChecked(False)
    # Old combined near-neutral greys: 20 steps, 2 rings, offset 4 (+ greysmid).
    # Spell out the other (old-format) sets as off so _apply_gen_sets doesn't
    # fall them back to the factory ON state — isolating the migrated total.
    legacy_cb = {n: False for n in
                 ("cube", "corners", "spirals", "skin", "blues", "greens",
                  "sunrises", "flamingos", "edges", "hs", "pastel", "image",
                  "whiteblack", "fill", "unique")}
    legacy_cb.update({"greys": True, "greysmid": True})
    legacy = {"cb": legacy_cb,
              "sp": {"greys_n": 20, "greys_rings": 2, "greys_off": 4,
                     "greysmid_n": 3}}
    dlg._apply_gen_sets(legacy)
    # greys → ramp(20) on + near-neutrals(20, rings 2) on; greysmid dropped.
    assert dlg._gen_neutral.isChecked() and dlg._gen_neutral_n.value() == 20
    assert dlg._gen_nearneutral.isChecked()
    assert dlg._gen_nearneutral_n.value() == 20
    assert dlg._gen_nearneutral_rings.value() == 2
    assert dlg._gen_nearneutral_off.value() == 4
    dlg._update_gen_counts()
    # Total matches the old combined: 20 + 20·(6+12) = 20 + 360 = 380.
    assert len(dlg._build_generated_program()) == 380


def test_legacy_greys_off_with_zero_rings_migrates_cleanly(qapp):
    """Old pure-ramp greys (rings 0) → Neutral grey ramp on, Near-neutral greys
    off; and an absent-key state loads the new generators at factory."""
    dlg = _AddPatchesDialog(_FakeSettings())
    dlg._apply_gen_sets({"cb": {"greys": True},
                         "sp": {"greys_n": 10, "greys_rings": 0}})
    assert dlg._gen_neutral.isChecked() and dlg._gen_neutral_n.value() == 10
    assert dlg._gen_nearneutral.isChecked() is False     # no rings → no set


def test_absent_checkbox_loads_off_not_factory(qapp):
    """A preset that omits a generator key loads it OFF, even though several
    sets are factory-ON — so a preset made before Flamingos existed doesn't come
    up with Flamingos enabled (Knut)."""
    dlg = _AddPatchesDialog(_FakeSettings())
    # A partial recipe: only the cube is specified.
    dlg._apply_gen_sets({"cb": {"cube": True}, "sp": {"cube_n": 6}})
    assert dlg._gen_cube.isChecked() is True
    # Factory-ON sets that the recipe didn't mention must be off, not on.
    assert dlg._gen_flamingos.isChecked() is False
    assert dlg._gen_skin.isChecked() is False
    assert dlg._gen_neutral.isChecked() is False


def test_legacy_edges_auto_migrates_to_between_one(qapp):
    """A pre-rework Saturated-edges state (the 'edges_auto' flag + 'edges_n' as a
    per-edge density) loads with 'between' reset to 1, not the old number that
    would over-generate (Knut)."""
    dlg = _AddPatchesDialog(_FakeSettings())
    dlg._apply_gen_sets({"cb": {"edges": True, "edges_auto": False},
                         "sp": {"edges_n": 5}})
    assert dlg._gen_edges.isChecked() is True
    assert dlg._gen_edges_n.value() == 1                  # reset from old 5
    assert dlg._gen_edges_faces.value() == 0


def test_neutral_ramp_steps_capped_at_64(qapp):
    """Both neutral generators cap their step count at 64."""
    dlg = _AddPatchesDialog(_FakeSettings())
    dlg._gen_neutral_n.setValue(999)
    assert dlg._gen_neutral_n.value() == 64
    dlg._gen_nearneutral_n.setValue(999)
    assert dlg._gen_nearneutral_n.value() == 64


def test_builtin_recipes_listed_in_load_setup_pulldown(qapp):
    """The 'Load setup from preset' pulldown lists the built-in presets that
    carry a recipe (★), registry-driven — not just local presets (Knut)."""
    from pathlib import Path
    d = _NewChartDialog(Path("/x"), _FakeSettings())
    recipes = d._available_preset_recipes()
    starred = [k for k in recipes if k.startswith("★")]
    assert starred, "no built-in recipes surfaced in the pulldown"
    # Each carries a real recipe dict.
    assert all(isinstance(recipes[k], dict) and recipes[k] for k in starred)


def test_fill_to_pages_target(qapp, tmp_path):
    """'fill to N pages' multiplies by the engine's capacity per page; disabled
    when the engine is off (#93)."""
    from pathlib import Path
    from workflow.layout_engine import geometry, instruments, papers
    from workflow.layout_engine.presets import default_recipe
    s = _FakeSettings(); s.set("use_chromiq_layout_engine", True)
    rec = default_recipe("i1", "A4", mode="clip")
    d = _NewChartDialog(tmp_path, s, initial_recipe=rec.to_dict())
    per = d._engine_cap_per_page()
    assert per > 0
    d._gen_fill_to.setValue(900)        # patches spin
    d._gen_fill_pages.setValue(2)       # pages spin (separate)
    # patches mode → the patches spin
    d._gen_fill_unit_patches.setChecked(True)
    assert d._effective_fill_target() == 900
    # pages mode → pages spin × capacity
    d._gen_fill_unit_pages.setChecked(True)
    assert d._effective_fill_target() == 2 * per

    # engine off → no per-page capacity, 'pages' toggle disabled + reverts
    s.set("use_chromiq_layout_engine", False)
    assert d._engine_cap_per_page() == 0
    d._sync_fill_unit()
    assert d._gen_fill_unit_patches.isChecked()
    assert not d._gen_fill_unit_pages.isEnabled()
