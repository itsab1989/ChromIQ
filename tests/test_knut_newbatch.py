"""Knut's new batch — G1..G5. Every assertion here FAILS on the current tree.

Each covers one of Knut's 4.1.3-beta.13 reports:
  G1  a preset with an empty project name invented one
  G2  keyboard shortcuts were missing from tooltips (and three said "Ctrl" on a Mac)
  G3  help text describing a button that had moved
  G4  file dialogs opening in $HOME instead of the ChromIQ folder
  G5  the preset swap
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from ui.tooltip_button import InfoDialog

@pytest.fixture
def settings(tmp_path):
    """A sandboxed AppSettings, pointed at a scratch working folder.

    The agent that wrote these tests supplied this from its own conftest; the
    repo's conftest already sandboxes QSettings per worker, so this only has to
    add the per-test output path.
    """
    from core.settings import AppSettings

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("session_project", "")
    s.set("restore_last_session", False)
    return s



from core.argyll_runner import ArgyllRunner
from core.file_manager import FileManager
from ui.tabs.tab_chart import TabChart


def _tab(qapp, settings):
    t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    return t


# ---------------------------------------------------------------------------
# G1 — a chart built from a .ti1 must never invent a project name
# ---------------------------------------------------------------------------

def test_g1_generate_from_ti1_asks_instead_of_inventing(qapp, settings, monkeypatch):
    """The beta.14 guard belongs at the door of the build, not on one road to it.

    `_generate_from_ti1` is reached by SEVEN routes that skip `_on_generate`'s
    check — a user preset with an attached .ti1 being the one Knut hit — and it
    calls the mutating `get_target_name()`, which makes up
    `Printer_Paper_Type_Instr_<timestamp>` and builds the whole chart into it.
    """
    from ui.tabs.tab_chart import KNUT_PRESETS
    from core.resource_path import resource_path
    tab = _tab(qapp, settings)
    ti1 = resource_path([p for p in KNUT_PRESETS
                         if p.slug.startswith("i1_w8")][0].ti1_asset)
    built, asked = [], []
    monkeypatch.setattr(tab._creator, "load_ti1_and_generate_preview",
                        lambda *a, **k: built.append(a))
    monkeypatch.setattr(tab, "_ask_for_a_project_name", lambda **kw: asked.append(kw.get("retry")))

    tab._manual_target_name_edit.setText("")          # nothing typed
    assert not tab._file_mgr.is_named()               # nothing open
    tab._generate_from_ti1(ti1, ask=False)

    assert asked, "it must ask for a project name"
    assert not built, "it must not build a chart into a name nobody chose"
    assert not tab._file_mgr.is_named(), (
        f"a name was invented: {tab._file_mgr._target_name!r}")
    assert tab._generate_btn.isEnabled(), \
        "an early return must re-enable Generate Chart"


def test_g1_a_user_preset_with_an_attached_ti1_does_not_invent(qapp, settings,
                                                               tmp_path, monkeypatch):
    """Knut's exact route: Presets ▸ a saved preset that bundles its patch set.

    Both of the options that make it reproduce — "generate on select" and
    "attach the patch set" — are ON by default in the Save Preset dialog
    (`_preset_save_prefill`), so this is the ordinary preset, not an exotic one.
    """
    import core.preset_store as ps
    from core.resource_path import resource_path
    from ui.tabs.tab_chart import KNUT_PRESETS

    store = tmp_path / "presets"
    monkeypatch.setattr(ps, "presets_dir", lambda: store)
    name = "My i1Pro A4 setup"
    d = ps.tab_dir("create_chart")
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.json").write_text(json.dumps(
        {"chromiq_preset_version": 1, "tab": "create_chart", "name": name,
         "data": {"auto_run": True, "attached_ti1": True,
                  "printtarg_-i": "i1", "printtarg_-p": "A4"}}))
    shutil.copy(resource_path([p for p in KNUT_PRESETS
                               if p.slug.startswith("i1_w8")][0].ti1_asset),
                ps.sidecar_path("create_chart", name, ".ti1"))

    tab = _tab(qapp, settings)
    built, asked = [], []
    monkeypatch.setattr(tab._creator, "load_ti1_and_generate_preview",
                        lambda *a, **k: built.append(a))
    # The fix ASKS for a name, so the real dialog would now open here — stub it
    # and assert it was reached. (Before the fix nothing was asked at all.)
    monkeypatch.setattr(type(tab), "_ask_for_a_project_name",
                        lambda self, **kw: asked.append(kw.get("retry")))
    tab._refresh_preset_combo() if hasattr(tab, "_refresh_preset_combo") else None
    idx = tab._preset_combo.findData(name)
    assert idx > 0, "the user preset should be in the dropdown"

    tab._manual_target_name_edit.setText("")
    # A REAL CLICK. The presets dropdown is wired to `activated`, which Qt emits
    # only for an interaction, so moving the combo from code is silent (#175).
    tab._preset_combo.blockSignals(True)
    tab._preset_combo.setCurrentIndex(idx)
    tab._preset_combo.blockSignals(False)
    tab._preset_combo.activated.emit(idx)

    assert not tab._file_mgr.is_named(), (
        f"selecting a preset invented {tab._file_mgr._target_name!r}")
    assert not built, "no chart may be built before the project has a name"
    assert asked, "the user was not asked for a name — nothing told them why"
    assert asked[0] and "preset" in asked[0], (
        f"the message should name the way back for a PRESET, got {asked[0]!r}")


def test_g1_the_displacement_question_never_creates_a_project(qapp, settings):
    """A question must have no side effects. `_confirm_displacing_results` goes
    through `_target_run()` → `FileManager.project()`, which CREATES the folder
    and the manifest — so merely asking "is anything at risk?" can invent a
    project when none is open."""
    tab = _tab(qapp, settings)
    tab._target_ctl = None                 # no run bar: the guard at :11675 is gone
    assert tab._confirm_displacing_results() is True
    assert not tab._file_mgr.is_named(), (
        f"the question invented {tab._file_mgr._target_name!r}")
    root = Path(settings.get("custom_output_path"))
    assert not (root.exists() and any(root.iterdir())), \
        f"the question created {sorted(p.name for p in root.iterdir())}"


# ---------------------------------------------------------------------------
# G2 — shortcuts belong in the tooltips, derived from one registry
# ---------------------------------------------------------------------------

def test_g2_there_is_one_shortcut_registry():
    from ui import keyboard_help
    assert hasattr(keyboard_help, "BINDINGS"), \
        "shortcuts must be declared in one place, not typed twice"
    for action in ("open_project", "open_chart_file", "preferences",
                   "tools", "help", "primary_action"):
        assert action in keyboard_help.BINDINGS


def test_g2_main_window_installs_from_the_registry():
    """No literal key sequence may be typed into _install_shortcuts."""
    import inspect
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._install_shortcuts)
    literals = re.findall(r'sc\(\s*(["\'])((?:Ctrl|Shift|Alt|Meta|F\d)[^"\']*)\1',
                          src)
    assert not literals, f"hand-typed bindings: {[l[1] for l in literals]}"


def test_g2_masthead_tooltips_carry_their_shortcut(qapp, settings):
    from PyQt6.QtGui import QKeySequence
    from ui.keyboard_help import keys_for
    from ui.masthead_header import MastheadHeader
    m = MastheadHeader(None) if MastheadHeader.__init__.__code__.co_argcount == 2 \
        else MastheadHeader()
    for attr, action in (("_load_project_btn", "open_project"),
                         ("_load_ti2_btn", "open_chart_file"),
                         ("_btn", "preferences"),
                         ("_tools_btn", "tools")):
        tip = getattr(m, attr).toolTip()
        k = keys_for(action)
        assert k and k in tip.splitlines()[0], \
            f"{attr}: {tip.splitlines()[0]!r} does not show {k!r}"


#: keyboard_help.py IS the source of truth — it may name the modifier key.
_SHORTCUT_TEXT_ALLOWED = {"keyboard_help.py"}


def test_g2_no_shortcut_is_hand_typed_into_a_translatable_string():
    """A key sequence inside tr() is a shortcut that will rot in 13 catalogues.

    Every string literal that is an argument to tr() is read from the AST, so an
    implicitly-concatenated multi-line tooltip is seen whole.
    """
    import ast
    bad = []
    for p in sorted(Path("/Users/Basti/develop/ChromIQ/ui").rglob("*.py")):
        if p.name in _SHORTCUT_TEXT_ALLOWED:
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Call)
                    and getattr(n.func, "id", None) == "tr"):
                continue
            for a in n.args:
                if not (isinstance(a, ast.Constant)
                        and isinstance(a.value, str)):
                    continue
                # "⌘/Ctrl + scroll" spells BOTH platforms out and is
                # therefore correct everywhere — it is generic canvas-zoom
                # prose, not one of ChromIQ's own bindings, and there is
                # nothing in BINDINGS to derive it from. What this test is
                # for is a string that names ONE platform's key and is
                # therefore wrong on the others, which is how the editor's
                # tooltips came to tell Mac users to press Ctrl.
                if re.search(r"[⌘⇧⌥⌃]\s*/\s*(?:Ctrl|Cmd)", a.value):
                    continue
                if re.search(r"[⌘⇧⌥⌃]|\b(?:Ctrl|Cmd|Command)\s*\+", a.value):
                    bad.append(f"{p.name}:{n.lineno}: {a.value[:70]!r}")
    assert not bad, ("shortcuts hand-typed inside tr() — derive them from "
                     "keyboard_help.BINDINGS instead:\n  " + "\n  ".join(bad))


# ---------------------------------------------------------------------------
# G3 — no help text may describe a button that moved
# ---------------------------------------------------------------------------

def test_g3_create_chart_help_does_not_send_you_to_the_reveal_folder_button(qapp, settings):
    """The Create Chart title help sent beginners to "the magenta folder button
    in the header (top right)" for Open Project. That button moved to the
    masthead top LEFT in #130 — and a magenta folder button really is still in
    the Create Chart header top right: Reveal Folder."""
    src = Path("/Users/Basti/develop/ChromIQ/ui/tabs/tab_chart.py").read_text()
    assert "magenta folder button" not in src
    assert "use the folder icon to\n" not in src and \
           "use the folder icon to " not in src


def test_g3_the_gear_is_not_at_the_top_left():
    src = Path("/Users/Basti/develop/ChromIQ/ui/tabs/tab_profile.py").read_text()
    assert "the gear at the top left" not in src, \
        "the settings gear is a top-RIGHT masthead child (masthead_header.py:96)"


# ---------------------------------------------------------------------------
# G4 — a ChromIQ file dialog starts in the ChromIQ folder
# ---------------------------------------------------------------------------

def test_g4_a_dialog_with_no_start_dir_does_not_open_in_home(qapp, settings,
                                                             tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog
    import ui.widgets as W
    root = tmp_path / "out"
    root.mkdir(parents=True, exist_ok=True)
    seen = []
    monkeypatch.setattr(QFileDialog, "exec",
                        lambda self: seen.append(self.directory().absolutePath())
                        or QFileDialog.DialogCode.Rejected)
    W.open_file_dialog(None, "t", "TI2 files (*.ti2)", extra_path=str(root))
    assert seen and seen[0] != str(Path.home()), \
        "a ChromIQ browse must not start in the user's home folder"
    assert seen[0] == str(root)


def test_g4_the_ti2_button_starts_in_the_chromiq_folder(qapp, settings,
                                                        tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog
    from ui.tabs.tab_measure import TabMeasure
    root = Path(settings.get("custom_output_path"))
    root.mkdir(parents=True, exist_ok=True)
    tab = TabMeasure(ArgyllRunner(settings), settings)
    seen = []
    monkeypatch.setattr(QFileDialog, "exec",
                        lambda self: seen.append(self.directory().absolutePath())
                        or QFileDialog.DialogCode.Rejected)
    tab._on_load_ti2()
    assert seen and seen[0] == str(root), \
        f"'Open Chart File (.ti2)' opened in {seen[0] if seen else '(nothing)'}"


# ---------------------------------------------------------------------------
# G5 — the preset swap
# ---------------------------------------------------------------------------

_GONE = {"fls_i1pro_a4_924p_2pages_portrait",
         "fls_i1pro_a4_924p_2pages_portrait_nature_focus"}


def test_g5_the_two_withdrawn_full_layout_charts_are_gone():
    from core.resource_path import resource_path
    from ui.tabs.tab_chart import KNUT_PRESETS
    slugs = {p.slug for p in KNUT_PRESETS}
    assert not (slugs & _GONE)
    for slug in _GONE:
        assert not resource_path(
            f"assets/charts/knut/rgb/fulllayout/{slug}").exists()


def test_g5_the_nineteen_new_i1pro_charts_are_registered():
    from ui.tabs.tab_chart import KNUT_PRESETS
    new = [p for p in KNUT_PRESETS if p.slug.startswith("i1_w75_")]
    assert len(new) == 19
    assert sum(1 for p in new if p.layout_recipe["paper"] == "A4") == 8
    assert sum(1 for p in new if p.layout_recipe["paper"] == "Letter") == 8
    assert sum(1 for p in new if p.layout_recipe["paper"] == "420x297") == 3
    assert all("w7.5mm" in p.name for p in new)
    # None of the 8 mm charts moved.
    assert sum(1 for p in KNUT_PRESETS if p.slug.startswith("i1_w8_")) == 19


def test_g5_the_page_count_comes_from_the_chart_not_the_payload():
    """18 of Knut's 19 exports carry data.pages = 4 whatever their name says.
    Taking that number would ship every one of them as a 4-page chart."""
    from ui.tabs.tab_chart import KNUT_PRESETS
    new = [x for x in KNUT_PRESETS if x.slug.startswith("i1_w75_")]
    assert len(new) == 19          # never vacuous
    for p in new:
        said = int(re.search(r"-(\d+)pages?-", p.name).group(1))
        per_page = p.layout_recipe["area_cols"] * p.layout_recipe["area_rows"]
        assert p.pages == said
        assert -(-p.patches // per_page) == p.pages


def test_g5_the_new_family_keeps_its_own_base():
    """Knut's 7.5 mm charts are NOT the 8 mm family: they leave 4 mm at the
    right edge on A4/A3 (against 6) and scale spacers at 0.75 (against 0.8).
    Built through _I1_BASE the A4 patch comes out 7.41 mm (its 6.0 mm right
    margin, not its sscale — that one scales SPACERS) against the 7.49 mm these
    actually print, and the ±0.5 mm build check would not notice."""
    from ui.tabs.tab_chart import _I1_BASE, KNUT_PRESETS
    new = [p for p in KNUT_PRESETS if p.slug.startswith("i1_w75_")]
    assert new
    for p in new:
        assert p.layout_recipe["sscale"] == 0.75
        if p.layout_recipe["paper"] in ("A4", "420x297"):
            assert p.layout_recipe["margin_right"] == 4.0
        else:
            assert p.layout_recipe["margin_right"] == 9.0
    assert _I1_BASE["sscale"] == 0.8          # the 8 mm family is untouched
    assert _I1_BASE["margin_right"] == 6.0


def test_g5_the_importer_knows_the_new_family():
    from scripts.import_knut_presets import FAMILIES
    fam = [f for f in FAMILIES.values() if f.slug_prefix == "i1_w75_"]
    assert fam, "a fourth family is a table entry, not a script (its docstring)"
    assert fam[0].dest.name != "i1pro", \
        "the 7.5 mm charts must not land on top of the 8 mm ones"
