#!/usr/bin/env python3
"""Does every instrument behave like the others on the Create Chart tab?

This is the library behind ``tests/test_instrument_parity.py`` and
``scripts/instrument_parity_drive.py``. It OBSERVES the app and changes
nothing: it builds the real Create Chart tab (``TabChart``) on a throwaway
settings file, chooses each instrument the way a person's click does (the
combo's index, then its ``activated`` signal), and records what it sees.

Every instrument is compared with the REFERENCE instrument, the i1Pro strip
reader (``i1``): printtarg's default, the first entry of every list, and the
instrument every Create Chart option was built for first. Five aspects:

  a. controls   every input on the Guided and the Manual page: shown or not,
                enabled or greyed, the value a fresh start shows, and, for a
                control greyed for this instrument only, a reason the person
                can read (its tooltip or an (i) button beside it);
  b. kept       every option survives Save as Defaults (and the next start),
                the preset bar, a named preset and the target's own settings;
  c. switching  choosing A, then B, then A again gives A back what it had,
                and B takes over only the values the allow-list calls shared;
  d. run types  every run type the app has can be chosen and built for it;
  e. label style  Preferences > Chart Layout's label style reaches a chart the
                same way in Guided and in Manual as it does for the reference.

Instruments are DISCOVERED (Guided's list, printtarg's ``-i`` choices in
``data/parameters.yaml``, the layout panel's list and
``data.patch_db.INSTRUMENT_LABELS``), and every Beta switch module
(``workflow/<name>/support.py`` with ``set_enabled_for_this_process``) is
switched on, so a new instrument is checked without editing anything here.

Differences from the reference are allowed only when they are written down,
with a reason, in ``tests/data/instrument_parity_allowlist.json``. To see what
your instrument does differently, ready to paste into that file::

    QT_QPA_PLATFORM=offscreen python scripts/instrument_parity.py

(add ``--only CODE`` to see one instrument). It needs no ArgyllCMS, no
printer and no window, and touches no real settings.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import os
import sys
import tempfile
from dataclasses import fields, replace
from pathlib import Path
from typing import Any, Iterator

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

REFERENCE = "i1"
ALLOWLIST = REPO / "tests" / "data" / "instrument_parity_allowlist.json"
#: "manual_engine_off" is Manual with the ChromIQ layout engine switched off
#: (printtarg lays the chart out; the instrument is printtarg's -i row).
MODES = ("guided", "manual", "manual_engine_off")

#: Check kinds, in the order the allow-list is written.
CHECKS = ("listed", "control", "greyed_without_reason", "kept",
          "switch_back", "inherits", "run_type", "prefs_style")

#: Not options a person sets for a chart, so the generic "change it and see
#: whether it is kept" walk leaves them alone. Everything else is walked.
NOT_WALKED = {
    "_instr_combo": "the instrument itself; checked by the switching walk",
    "panel.instr": "the instrument itself; checked by the switching walk",
    "pw.printtarg-i": "the instrument itself; checked by the switching walk",
    "_manual_instr_pw": "the instrument itself; checked by the switching walk",
    "_preset_combo": "choosing a preset applies it; walked by the preset paths",
    "_manual_engine_check": "switches the layout engine and with it the whole "
                            "panel; walked by the panel's own paths",
    "_target_name_edit": "the project's name: a new one starts or renames a "
                         "project, which is not a chart option",
    "_manual_target_name_edit": "the project's name, as in Guided",
}

#: A value each LayoutRecipe field can take that is not its default. Fields
#: whose value the panel gives back for an instrument are that instrument's
#: options, and each must survive every path. A recipe field added later and
#: missing here fails ``test_every_recipe_field_has_a_candidate``.
CANDIDATES: dict[str, Any] = {
    "paper": "Letter", "dpi": 400, "randomize": False, "spacer_mode": "bw",
    "edge_spacers": True, "margin_top": 14.0, "margin_right": 17.0,
    "margin_bottom": 30.0, "margin_left": 40.0, "patch_w_mm": 11.0,
    "patch_h_mm": 9.0, "spacer_width_mm": 1.5, "inter_patch_mm": 0.5,
    "strip_gap_mm": 1.5, "max_strip_mm": 200.0, "strip_indicator_gap_mm": 1.0,
    "offset_x_mm": 1.5, "offset_y_mm": 1.0, "bit16": True,
    "compression": "none", "export_pdf": True, "show_strip_indicators": False,
    "show_row_indicators": False, "indicator_font": "Inter",
    "indicator_size_mm": 3.0, "indicator_bold": True, "indicator_italic": True,
    "indicator_align": "center", "strip_label_offset_mm": 1.0,
    "strip_label_offset_x_mm": 0.5, "underline_mode": "black",
    "underline_thickness_mm": 0.8, "underline_gap_mm": 0.7,
    "chart_text": "Lot 7", "chart_text_font": "JetBrains Mono",
    "chart_text_size_mm": 3.0, "chart_text_italic": True,
    "helper_markers": True, "helper_marker_edge_mm": 3.0,
    "helper_marker_len_mm": 3.0, "helper_marker_per_patch": 2,
    "helper_markers_top_bottom": False, "helper_markers_sides": False,
    "text_edge_mm": 6.0, "clip_border_width_mm": 30.0,
    "clip_content_mode": "text", "clip_text": "Paper: Hahnemuehle",
    "clip_text_font": "JetBrains Mono", "clip_text_size_mm": 3.0,
    "clip_flip_180": True, "nolimit": True, "strip_pattern": "1-9, 1-9",
    "patch_pattern": "A-Z;1-999",
    # the options of one instrument family each
    "i1io_crosses": False, "i1io_align": "center", "i1io_clip_border": True,
    "i1io_text_bold": False, "i1io_numbers_edge_mm": 7.0,
    "i1io_text_align": "start", "hflag": True, "cm_density": 2,
    "cm_stagger": True, "hex_flat_top": True, "fd9_gap_mm": 2.0,
    "fd9_clip_border": True,
    # the rest of the panel
    "pscale": 1.1, "sscale": 1.2, "use_instrument_margins": False,
    "indicator_rotation": 90, "row_indicator_rotation": 180,
    "patch_area_align": "center", "chart_text_bold": True,
    "chart_text_align": "center", "text_edge_top_mm": 5.0,
    "text_edge_clip_mm": 5.0, "stamp_command": True, "clip_side": "right",
    "layout_mode": "patch_first", "area_method": "by_grid", "area_cols": 9,
    "area_rows": 7, "area_ratio": 1.3, "area_min_patch_mm": 7.0,
}

#: Recipe fields that are not an option of their own, and why.
NOT_A_CANDIDATE = {
    "instrument": "the instrument itself",
    "seed": "the shuffle seed of one build",
    "seed_fixed": "kept by the randomisation row",
    "spacer_on": "follows spacer_mode ('none' is off)",
    "spacer_palette": "the coloured spacers' palette, set by its own dialog",
    "spacer_overrides": "per-pair spacer colours, internal",
    "border": "printtarg's single border, superseded by the four margins",
    "i1io_label_options": "a recipe's version mark",
    "layout_explicit": "bookkeeping",
    "margins_explicit": "bookkeeping",
    "align_explicit": "bookkeeping",
    "label_style_explicit": "bookkeeping",
    "clip_border": "derived from the panel's clip selector",
    "clip_content_when_on": "remembered content mode while the band is off",
    "clip_image_path": "a file path",
    "clip_image_rotation": "image content only",
    "clip_image_scale": "image content only",
    "clip_image_offset_x_mm": "image content only",
    "clip_image_offset_y_mm": "image content only",
    "clip_border_free_space": "derived from the content mode",
}

#: The Preferences > Chart Layout label style the e-walk sets.
PREFS_STYLE = {"strip_indicator_font": "Inter", "strip_indicator_bold": True,
               "strip_underline_mode": "black",
               "strip_indicator_size_mm": 3.0,
               "strip_indicator_align": "center"}


# ---------------------------------------------------------------------------
# Beta switches and the instrument lists
# ---------------------------------------------------------------------------

def beta_support_modules() -> list:
    """Every ``workflow/<name>/support.py`` that is a Beta switch."""
    out = []
    for path in sorted((REPO / "workflow").glob("*/support.py")):
        try:
            mod = importlib.import_module(f"workflow.{path.parent.name}.support")
        except Exception:      # noqa: BLE001 - a module that cannot load is no switch
            continue
        if callable(getattr(mod, "set_enabled_for_this_process", None)):
            out.append(mod)
    return out


@contextlib.contextmanager
def betas_on() -> Iterator[list[str]]:
    """Every Beta instrument switched on for this process, then put back."""
    mods = beta_support_modules()
    before = [getattr(m, "_latched", None) for m in mods]
    for m in mods:
        m.set_enabled_for_this_process(True)
    try:
        yield [m.__name__ for m in mods]
    finally:
        for m, b in zip(mods, before):
            m.set_enabled_for_this_process(b)


def instrument_lists(tab) -> dict[str, list[str]]:
    """Every place Create Chart lists instruments, as the tab built them."""
    from data.patch_db import INSTRUMENT_LABELS
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    combo = tab._instr_combo
    return {
        "guided": [combo.itemData(i) for i in range(combo.count())],
        "printtarg": list(_printtarg_choices()),
        "layout_panel": [c for c, _ in LayoutOptionsPanel.instruments()],
        "labels": list(INSTRUMENT_LABELS),
    }


def registries() -> dict[str, list[str]]:
    """Other places that name instruments by code. Not used to DISCOVER
    instruments (some hold codes the app no longer offers); an instrument
    that is in the reference's lists but missing from one is reported."""
    from ui.dialogs.settings_dialog import SettingsDialog
    from ui.dialogs.ti2_relayout_dialog import _INSTRUMENTS as relayout
    from ui.ti2_loader import KNOWN_INSTRUMENTS
    from workflow.chart_creator import ENGINE_INSTRUMENTS
    from workflow.layout_engine import instruments, presets
    names = instruments.TARGET_INSTRUMENT_NAME
    return {
        "engine.supported()": list(instruments.supported()),
        "presets.SUPPORTED_INSTRUMENTS": list(presets.SUPPORTED_INSTRUMENTS),
        "chart_creator.ENGINE_INSTRUMENTS": sorted(ENGINE_INSTRUMENTS),
        "TARGET_INSTRUMENT_NAME": list(names),
        "Preferences chart layout": [c for c, _ in
                                     SettingsDialog._LAYOUT_INSTRUMENTS],
        "ti2 re-layout dialog": [{"3p": "p3"}.get(c, c) for c, _ in relayout],
        "ti2_loader.KNOWN_INSTRUMENTS": [c for c, n in names.items()
                                         if n in KNOWN_INSTRUMENTS],
    }


def _printtarg_choices() -> list[str]:
    import yaml
    data = yaml.safe_load((REPO / "data" / "parameters.yaml").read_text(
        encoding="utf-8"))["parameters"]["printtarg"]
    for p in data:
        if p.get("flag") == "-i":
            return [c.get("value") if isinstance(c, dict) else c
                    for c in p.get("choices") or []]
    return []


def all_instruments(lists: dict[str, list[str]]) -> list[str]:
    """The union of every list, reference first, then printtarg's order."""
    seen: list[str] = [REFERENCE]
    for name in ("printtarg", "guided", "layout_panel", "labels"):
        for c in lists.get(name, []):
            if c and c not in seen:
                seen.append(c)
    return seen


# ---------------------------------------------------------------------------
# A fresh Create Chart tab on its own settings file
# ---------------------------------------------------------------------------

class Bench:
    """Builds Create Chart tabs on throwaway settings files under *root*."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._n = 0
        self._alive: list = []

    def ini(self) -> Path:
        self._n += 1
        return self.root / f"settings-{self._n}.ini"

    def settings(self, ini: "Path | None" = None, prefs: "dict | None" = None,
                 engine: "bool | None" = None):
        from PyQt6.QtCore import QSettings
        from core.settings import AppSettings
        ini = ini or self.ini()
        s = AppSettings()
        s._qs = QSettings(str(ini), QSettings.Format.IniFormat)
        if not ini.exists() or not s.get("custom_output_path", ""):
            s.set("custom_output_path", str(self.root / f"out-{self._n}"))
        for k, v in (prefs or {}).items():
            s.set(k, v)
        if engine is not None:
            s.set("use_chromiq_layout_engine", bool(engine))
        s._parity_ini = ini
        return s

    def for_mode(self, mode: str, **kw):
        """A settings store for *mode* (the engine off for that mode)."""
        if mode == "manual_engine_off":
            kw["engine"] = False
        return self.settings(**kw)

    def tab(self, settings=None, *, project: "str | None" = None):
        """A Create Chart tab as a fresh start shows it (Guided showing)."""
        from core.argyll_runner import ArgyllRunner
        from core.file_manager import FileManager
        from ui.tabs.tab_chart import TabChart
        s = settings or self.settings()
        fm = FileManager(s)
        ctl = None
        if project:
            from ui.measurement_target_bar import MeasurementTargetController
            fm.set_target_name(project)
            proj = fm.project()
            if len(proj.all_runs()) < 2:
                proj.new_run()
        tab = TabChart(ArgyllRunner(s), fm, s)
        if project:
            ctl = MeasurementTargetController(fm)
            ctl.set_calibration_allowed(True)
            tab.set_target_controller(ctl)
            tab.set_calibration_mode(True)
        tab._parity_settings = s
        tab._parity_ctl = ctl
        tab._switch_mode("manual")
        tab._init_manual_layout_panel()
        tab._switch_mode("guided")
        if ctl is not None:
            ctl.set_profile_run(ctl.run_ids()[0])
        _settle()
        self._alive.append(tab)
        return tab

    def drop(self, tab) -> None:
        try:
            self._alive.remove(tab)
        except ValueError:
            pass
        try:
            tab.deleteLater()
        except RuntimeError:
            pass
        _settle()

    def close(self) -> None:
        for t in list(self._alive):
            self.drop(t)


#: Every window that would have waited for an answer during a walk:
#: (where, its class, its title, the start of its text). A walk answers
#: Cancel / No to every one of them, as a person who changes nothing would.
QUESTIONS: list[tuple] = []
_WHERE = ["start"]


@contextlib.contextmanager
def no_waiting_windows() -> Iterator[None]:
    """No modal window may wait for a person during a walk: record it and
    answer it with its reject button."""
    from PyQt6.QtWidgets import QDialog, QFileDialog, QMessageBox
    saved = {(QDialog, "exec"): QDialog.exec,
             (QMessageBox, "exec"): QMessageBox.exec,
             (QFileDialog, "getOpenFileName"): QFileDialog.getOpenFileName,
             (QFileDialog, "getSaveFileName"): QFileDialog.getSaveFileName,
             (QFileDialog, "getExistingDirectory"):
                 QFileDialog.getExistingDirectory}

    def _note(dlg) -> None:
        text = ""
        try:
            text = dlg.text() if hasattr(dlg, "text") else ""
        except Exception:      # noqa: BLE001
            pass
        QUESTIONS.append((_WHERE[0], type(dlg).__name__,
                          dlg.windowTitle(), (text or "")[:80]))

    def _dialog_exec(self, *a, **k):
        _note(self)
        return 0

    def _msg_exec(self, *a, **k):
        _note(self)
        no = self.escapeButton() or self.defaultButton()
        if no is not None:
            try:
                self.setProperty("_parity_answer", "escape")
                no.click()
            except Exception:      # noqa: BLE001
                pass
        return int(QMessageBox.StandardButton.Cancel.value)

    def _file(*a, **k):
        QUESTIONS.append((_WHERE[0], "QFileDialog", "", ""))
        return ("", "")

    def _dir(*a, **k):
        QUESTIONS.append((_WHERE[0], "QFileDialog", "", ""))
        return ""

    QDialog.exec = _dialog_exec
    QMessageBox.exec = _msg_exec
    QFileDialog.getOpenFileName = staticmethod(_file)
    QFileDialog.getSaveFileName = staticmethod(_file)
    QFileDialog.getExistingDirectory = staticmethod(_dir)
    try:
        yield
    finally:
        for (cls, name), fn in saved.items():
            setattr(cls, name, fn)


def _settle() -> None:
    from PyQt6.QtWidgets import QApplication
    QApplication.processEvents()


def pick(tab, mode: str, code: str) -> bool:
    """Choose *code* in *mode* the way a person does. False when that mode
    does not offer it."""
    if mode == "guided":
        tab._switch_mode("guided")
        combo = tab._instr_combo
    elif mode == "manual_engine_off":
        tab._switch_mode("manual")
        pw = _param(tab, "printtarg", "-i")
        if pw is None:
            return False
        pw.set_value(code)
        _settle()
        return tab._shared_get("manual")["instrument"] == code
    else:
        tab._switch_mode("manual")
        combo = tab._manual_layout_panel.instr
        if combo.findData(code) < 0:
            # not laid out by the panel (the external workflows): printtarg's
            # own -i row is what a person uses then
            pw = _param(tab, "printtarg", "-i")
            if pw is None:
                return False
            pw.set_value(code)
            _settle()
            return tab._shared_get("manual")["instrument"] == code
    i = combo.findData(code)
    if i < 0:
        return False
    combo.setCurrentIndex(i)
    combo.activated.emit(i)
    _settle()
    return True


def _param(tab, tool: str, flag: str):
    for pw in tab._manual_widgets.get(tool, []):
        if pw.flag == flag:
            return pw
    return None


# ---------------------------------------------------------------------------
# a. the controls
# ---------------------------------------------------------------------------

def _names(tab) -> dict[int, str]:
    from PyQt6.QtWidgets import QWidget
    names: dict[int, str] = {}

    panel = getattr(tab, "_manual_layout_panel", None)
    owners = [(p, o) for p, o in (("", tab), ("panel.", panel))
              if o is not None]
    # direct attributes first, then dicts (their keys mean something), then
    # lists: a widget the panel also keeps in a list is named by its own
    # attribute, a margin box by its side
    for prefix, obj in owners:
        for k, v in sorted(vars(obj).items()):
            if isinstance(v, QWidget):
                names.setdefault(id(v), prefix + k)
    for prefix, obj in owners:
        for k, v in sorted(vars(obj).items()):
            if isinstance(v, dict):
                for kk, vv in v.items():
                    if isinstance(vv, QWidget):
                        names.setdefault(id(vv), f"{prefix}{k}[{kk}]")
    for prefix, obj in owners:
        for k, v in sorted(vars(obj).items()):
            if isinstance(v, (list, tuple)) and len(v) < 50:
                for n, vv in enumerate(v):
                    if isinstance(vv, QWidget):
                        names.setdefault(id(vv), f"{prefix}{k}[{n}]")
    for tool, pws in tab._manual_widgets.items():
        for pw in pws:
            names[id(pw)] = f"pw.{tool}{pw.flag}"
    return names


def _inputs(root) -> list:
    from PyQt6.QtWidgets import (QAbstractButton, QAbstractSpinBox,
                                 QComboBox, QLineEdit, QSlider, QWidget)
    out = []
    for w in root.findChildren(QWidget):
        if isinstance(w, QLineEdit) and isinstance(
                w.parent(), (QComboBox, QAbstractSpinBox)):
            continue
        if isinstance(w, (QComboBox, QAbstractSpinBox, QLineEdit, QSlider)) \
                or (isinstance(w, QAbstractButton) and w.isCheckable()):
            out.append(w)
    return out


def _ident(w, names: dict[int, str], seen: dict[str, int]) -> str:
    from PyQt6.QtWidgets import QAbstractButton
    if id(w) in names:
        return names[id(w)]
    a = w.parent()
    while a is not None and id(a) not in names:
        a = a.parent()
    base = f"{names.get(id(a), '?')}/{type(w).__name__}"
    # never the button's text: it is translated and edited
    n = seen.get(base, 0)
    seen[base] = n + 1
    return base + (f"#{n}" if n else "")


def _value(w) -> Any:
    from PyQt6.QtWidgets import (QAbstractButton, QAbstractSpinBox,
                                 QComboBox, QLineEdit, QSlider)
    if isinstance(w, QComboBox):
        d = w.currentData()
        return d if isinstance(d, (str, int, float, bool)) else w.currentText()
    if isinstance(w, QAbstractButton):
        return w.isChecked()
    if isinstance(w, QAbstractSpinBox):
        v = w.value() if hasattr(w, "value") else w.text()
        return round(v, 4) if isinstance(v, float) else v
    if isinstance(w, QLineEdit):
        return w.text()
    if isinstance(w, QSlider):
        return w.value()
    return None


def _has_reason(w) -> bool:
    """A tooltip on the control or its row, or an (i) button beside it."""
    from ui.tooltip_button import TooltipButton
    x = w
    for _ in range(3):
        if x is None:
            break
        if (x.toolTip() or "").strip():
            return True
        x = x.parentWidget()
    parent = w.parentWidget()
    if parent is not None:
        for b in parent.findChildren(TooltipButton):
            if b.parentWidget() is parent and not b.isHidden():
                return True
    return False


def _open_sections(tab) -> None:
    from ui.widgets import CollapsibleGroupBox
    for g in tab.findChildren(CollapsibleGroupBox):
        if g.is_collapsed():
            g.set_collapsed(False)
    _settle()


def page_of(tab, mode: str):
    return tab._stack.widget(0 if mode == "guided" else 1)


def _ui_mode(mode: str) -> str:
    return "guided" if mode == "guided" else "manual"


def control_table(tab, mode: str) -> dict[str, dict]:
    """Every input on *mode*'s page: present, enabled, value, reason."""
    tab._switch_mode(_ui_mode(mode))
    _open_sections(tab)
    page = page_of(tab, mode)
    names = _names(tab)
    seen: dict[str, int] = {}
    out: dict[str, dict] = {}
    for w in _inputs(page):
        out[_ident(w, names, seen)] = {
            "present": w.isVisibleTo(page), "enabled": w.isEnabled(),
            "value": _value(w), "reason": _has_reason(w), "_w": w}
    return out


def _public(table: dict) -> dict:
    return {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")}
            for k, v in table.items()}


# ---------------------------------------------------------------------------
# b. kept
# ---------------------------------------------------------------------------

def _show(tab, rec) -> None:
    tab._set_manual_value("printtarg", "-p", rec.paper)
    tab._manual_layout_panel.set_recipe(rec)
    _settle()


def _same(a, b) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) < 1e-6
        except (TypeError, ValueError):
            return False
    return a == b


def _lost(rec, want: dict) -> list[str]:
    return sorted(k for k, v in want.items() if not _same(getattr(rec, k), v))


def _marked(rec):
    """*rec* as a person who set its options has it: the panel marks the
    groups a person touched, so Preferences' label style stays out of it."""
    return replace(rec, margins_explicit=True, align_explicit=True,
                   label_style_explicit=True, layout_explicit=True)


def recipe_options(tab, code: str) -> tuple[Any, dict]:
    """(the instrument's fresh recipe, {field: candidate} the panel keeps)."""
    pick(tab, "manual", code)
    panel = tab._manual_layout_panel
    base = panel.get_recipe()
    want = {k: v for k, v in CANDIDATES.items()
            if not _same(getattr(base, k), v)}
    _show(tab, _marked(replace(base, **want)))
    got = panel.get_recipe()
    kept = {k: v for k, v in want.items() if _same(getattr(got, k), v)}
    return base, kept


def other_run_and_back(tab) -> None:
    """The target's own stored settings: move the bar to the project's other
    run and back, as a person does; the tab files and reloads each run's."""
    ctl = tab._parity_ctl
    ids = ctl.run_ids()
    here = ctl.target.profile_run or ids[0]
    there = next(i for i in ids if i != here)
    ctl.set_profile_run(there)
    _settle()
    ctl.set_profile_run(here)
    _settle()


def kept_walk(bench: Bench, code: str) -> dict[str, list[str]]:
    """{path: [fields lost]} for the Manual panel's options of *code*."""
    out: dict[str, list[str]] = {}
    # (1) Save as Defaults, and the next start on the same store
    s = bench.settings()
    tab = bench.tab(s)
    base, kept = recipe_options(tab, code)
    out["_options"] = sorted(kept)
    tab._on_save_defaults()
    bench.drop(tab)
    tab2 = bench.tab(bench.settings(s._parity_ini))
    tab2._switch_mode("manual")
    out["save_defaults"] = _lost(tab2._manual_layout_panel.get_recipe(), kept)
    bench.drop(tab2)
    # (2) the preset bar: Update preset, show the factory, Reset to preset
    tab = bench.tab()
    base, kept = recipe_options(tab, code)
    tab._update_manual_preset()
    # the factory values on the SAME preset (instrument, paper and mode:
    # the clip border, the density, the patch shape)
    k = tab._manual_layout_panel.get_recipe()
    _show(tab, replace(base, paper=k.paper, cm_density=k.cm_density,
                       hflag=k.hflag, clip_border=k.clip_border))
    tab._reset_manual_to_preset()
    _settle()
    out["preset_bar"] = _lost(tab._manual_layout_panel.get_recipe(), kept)
    # (3) a named preset, through JSON as the file holds it
    _show(tab, _marked(replace(base, **kept)))
    data = json.loads(json.dumps({
        "printtarg_-i": code,
        "printtarg_-p": tab._manual_layout_panel.get_recipe().paper,
        "layout_recipe": replace(tab._pinned_layout_recipe(), seed=None,
                                 seed_fixed=None).to_dict()}))
    _show(tab, base)
    tab._restore_user_preset(data)
    _settle()
    out["named_preset"] = _lost(tab._manual_layout_panel.get_recipe(), kept)
    bench.drop(tab)
    # (4) the target's own stored settings: another run and back
    tab = bench.tab(project="Parity")
    base, kept = recipe_options(tab, code)
    other_run_and_back(tab)
    tab._switch_mode("manual")
    out["target_state"] = _lost(tab._manual_layout_panel.get_recipe(), kept)
    bench.drop(tab)
    return out


def _change(w) -> bool:
    """Change one control to another value a person could choose."""
    from PyQt6.QtWidgets import (QAbstractButton, QAbstractSpinBox,
                                 QComboBox, QLineEdit, QSlider)
    if isinstance(w, QComboBox):
        if w.count() < 2:
            return False
        w.setCurrentIndex((w.currentIndex() + 1) % w.count())
        w.activated.emit(w.currentIndex())
        return True
    if isinstance(w, QAbstractButton):
        w.click()
        return True
    if isinstance(w, QAbstractSpinBox) and hasattr(w, "value"):
        step = w.singleStep() if hasattr(w, "singleStep") else 1
        v = w.value()
        w.setValue(v + step if v + step <= w.maximum() else v - step)
        return True
    if isinstance(w, QLineEdit):
        if w.isReadOnly():
            return False
        w.setText((w.text() or "") + "7")
        w.editingFinished.emit()
        return True
    if isinstance(w, QSlider):
        w.setValue(w.value() + 1 if w.value() < w.maximum() else w.value() - 1)
        return True
    return False


def _walkable(name: str, row: dict, mode: str) -> bool:
    if not (row["present"] and row["enabled"]):
        return False
    if name in NOT_WALKED or name.split("/")[0] in NOT_WALKED:
        return False
    if mode != "guided" and name.startswith("panel."):
        return False                  # the recipe walk covers the panel
    return True


def _change_everything(tab, mode: str) -> dict:
    t = control_table(tab, mode)
    for name in sorted(t):
        if _walkable(name, t[name], mode):
            try:
                _change(t[name]["_w"])
            except Exception:      # noqa: BLE001 - a refusal is not a loss
                pass
            _settle()
    after = control_table(tab, mode)
    return {k: v["value"] for k, v in after.items() if _walkable(k, v, mode)}


def _lost_controls(tab, mode: str, want: dict) -> list[str]:
    t = control_table(tab, mode)
    return sorted(k for k, v in want.items()
                  if k not in t or not _same(t[k]["value"], v))


def widget_walk(bench: Bench, mode: str, code: str) -> dict[str, list[str]]:
    """Change every enabled control of *mode* (outside the layout panel) and
    see what Save as Defaults and the target's own state give back."""
    out: dict[str, list[str]] = {}
    s = bench.settings()
    tab = bench.tab(s)
    pick(tab, mode, code)
    want = _change_everything(tab, mode)
    tab._on_save_defaults()
    bench.drop(tab)
    tab2 = bench.tab(bench.settings(s._parity_ini))
    tab2._switch_mode(_ui_mode(mode))
    out["save_defaults"] = _lost_controls(tab2, mode, want)
    bench.drop(tab2)

    tab = bench.tab(project="Parity")
    pick(tab, mode, code)
    want = _change_everything(tab, mode)
    other_run_and_back(tab)
    tab._switch_mode(_ui_mode(mode))
    out["target_state"] = _lost_controls(tab, mode, want)
    bench.drop(tab)
    return out


# ---------------------------------------------------------------------------
# c. switching
# ---------------------------------------------------------------------------

def _panel_pick(tab, code: str):
    pick(tab, "manual", code)
    return tab._manual_layout_panel.get_recipe()


def switching_walk(bench: Bench, codes: list[str]) -> dict:
    """For every X: ref -> X -> ref and X -> ref -> X on the Manual panel."""
    panel_codes = [c for c in codes if _panel_offers(bench, c)]
    fresh = {}
    for c in panel_codes:
        tab = bench.tab()
        fresh[c] = _panel_pick(tab, c)
        bench.drop(tab)
    names = [f.name for f in fields(fresh[REFERENCE])
             if f.name not in NOT_A_CANDIDATE or f.name in (
                 "spacer_on", "clip_content_when_on")]
    out: dict = {}
    for x in panel_codes:
        if x == REFERENCE:
            continue
        for a, b in ((REFERENCE, x), (x, REFERENCE)):
            tab = bench.tab()
            _panel_pick(tab, a)
            panel = tab._manual_layout_panel
            want = {k: v for k, v in CANDIDATES.items() if k != "paper"}
            _show(tab, replace(panel.get_recipe(), **want))
            ra = panel.get_recipe()
            rb = _panel_pick(tab, b)
            ra2 = _panel_pick(tab, a)
            bench.drop(tab)
            out[(a, b)] = {
                "lost": sorted(n for n in names
                               if not _same(getattr(ra, n), getattr(ra2, n))),
                "inherited": sorted(
                    n for n in names
                    if _same(getattr(rb, n), getattr(ra, n))
                    and not _same(getattr(ra, n), getattr(fresh[b], n))),
            }
    return out


_PANEL_CODES: "list[str] | None" = None


def _panel_offers(bench: Bench, code: str) -> bool:
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    return code in [c for c, _ in LayoutOptionsPanel.instruments()]


# ---------------------------------------------------------------------------
# d. run types, e. Preferences label style
# ---------------------------------------------------------------------------

def run_type_walk(bench: Bench, mode: str, code: str) -> dict[str, str]:
    """Each run type chosen on the bar, THEN the instrument (choosing a run
    type opens that target's own settings, instrument included)."""
    from core.measurement_target import RUN_TYPES
    out = {}
    tab = bench.tab(bench.for_mode(mode), project="Parity")
    ctl = tab._parity_ctl
    try:
        for rt in RUN_TYPES:
            ctl.set_run_type(rt)
            _settle()
            if not pick(tab, mode, code):
                out[rt] = "instrument not offered"
                continue
            held = ctl.target.run_type == rt
            try:
                params = tab._collect_params()
                tab._creator._engine_kwargs(params)
                built = "builds"
                if rt == "calibration" and not getattr(params, "cal_target",
                                                       False):
                    built = "builds, but not as a calibration chart"
            except Exception as exc:      # noqa: BLE001 - recorded, not raised
                built = f"refused: {type(exc).__name__}"
            gen = tab._generate_btn.isEnabled()
            out[rt] = ("offered" if held else "not held") + \
                ("" if gen else ", Generate greyed") + f", {built}"
    finally:
        bench.drop(tab)
    return out


def prefs_style_walk(bench: Bench, mode: str, code: str) -> str:
    from core.settings import INDICATOR_STYLE_KEYS
    field_of = {v: k for k, v in INDICATOR_STYLE_KEYS.items()}
    tab = bench.tab(bench.for_mode(mode, prefs=PREFS_STYLE))
    try:
        if not pick(tab, mode, code):
            return "instrument not offered"
        try:
            kw = tab._creator._engine_kwargs(tab._collect_params())
        except Exception as exc:      # noqa: BLE001
            return f"no layout ({type(exc).__name__})"
        n = sum(1 for k, v in PREFS_STYLE.items()
                if _same(kw.get(field_of[k], object()), v))
        return ("follows Preferences" if n == len(PREFS_STYLE)
                else "ignores Preferences" if n == 0
                else f"follows {n} of {len(PREFS_STYLE)}")
    finally:
        bench.drop(tab)


# ---------------------------------------------------------------------------
# Everything, as rows
# ---------------------------------------------------------------------------

def observe(root: Path, only: "list[str] | None" = None,
            log=lambda *_: None) -> dict:
    """Run every walk once. Returns the raw observations."""
    bench = Bench(root)
    obs: dict = {}
    QUESTIONS.clear()
    stack = contextlib.ExitStack()
    stack.enter_context(no_waiting_windows())
    try:
        tab = bench.tab()
        obs["lists"] = instrument_lists(tab)
        bench.drop(tab)
        codes = all_instruments(obs["lists"])
        obs["registries"] = registries()
        if only:
            codes = [c for c in codes if c == REFERENCE or c in only]
        obs["instruments"] = codes
        obs["controls"] = {}
        for mode in MODES:
            for code in codes:
                tab = bench.tab(bench.for_mode(mode))
                if pick(tab, mode, code):
                    obs["controls"][(mode, code)] = _public(
                        control_table(tab, mode))
                bench.drop(tab)
        log("controls done")
        obs["kept"] = {}
        for code in codes:
            if _panel_offers(bench, code):
                _WHERE[0] = f"kept manual {code}"
                obs["kept"][("manual", code)] = kept_walk(bench, code)
        for mode in ("guided", "manual"):
            for code in codes:
                if (mode, code) in obs["controls"]:
                    _WHERE[0] = f"kept controls {mode} {code}"
                    w = widget_walk(bench, mode, code)
                    obs["kept"].setdefault((mode, code), {})
                    for path, lost in w.items():
                        obs["kept"][(mode, code)]["controls:" + path] = lost
        log("kept done")
        _WHERE[0] = "switching"
        obs["switching"] = switching_walk(bench, codes)
        _WHERE[0] = "run types"
        log("switching done")
        obs["run_types"] = {(m, c): run_type_walk(bench, m, c)
                            for m in MODES for c in codes}
        log("run types done")
        obs["prefs_style"] = {(m, c): prefs_style_walk(bench, m, c)
                              for m in MODES for c in codes}
        log("prefs style done")
    finally:
        bench.close()
        stack.close()
    obs["questions"] = list(QUESTIONS)
    return obs


def _is_selector(name: str) -> bool:
    return name.split("/")[0] in ("_instr_combo", "panel.instr",
                                  "pw.printtarg-i", "_manual_instr_pw")


def differences(obs: dict) -> list[dict]:
    """Every row in which an instrument is not like the reference, or in
    which something a person set is not kept. Each row is one allow-list
    key plus the observed state as ``expected``."""
    rows: list[dict] = []
    codes = obs["instruments"]

    def add(check, mode, code, item, aspect, expected, reference=None):
        rows.append({"check": check, "mode": mode, "instrument": code,
                     "item": item, "aspect": aspect, "expected": expected,
                     **({"reference": reference} if reference is not None
                        else {})})

    lists = {**obs["lists"], **obs.get("registries", {})}
    for code in codes:
        for name, members in lists.items():
            if (code in members) != (REFERENCE in members):
                add("listed", "", code, name, "listed", code in members)

    for mode in MODES:
        ref = obs["controls"].get((mode, REFERENCE), {})
        for code in codes:
            t = obs["controls"].get((mode, code))
            if t is None:
                continue
            for name in sorted(set(ref) | set(t)):
                a, b = ref.get(name), t.get(name)
                if b is None or a is None:
                    add("control", mode, code, name, "exists", b is not None,
                        a is not None)
                    continue
                for aspect in ("present", "enabled", "value"):
                    if aspect == "value" and _is_selector(name):
                        continue      # it shows the instrument chosen
                    if code != REFERENCE and not _same(a[aspect], b[aspect]):
                        add("control", mode, code, name, aspect, b[aspect],
                            a[aspect])
                if (b["present"] and not b["enabled"] and a["enabled"]
                        and not b["reason"]):
                    add("greyed_without_reason", mode, code, name, "reason",
                        False)

    for (mode, code), paths in sorted(obs["kept"].items()):
        for path, lost in sorted(paths.items()):
            if path.startswith("_"):
                continue
            for item in lost:
                add("kept", mode, code, item, path, "lost")

    for (a, b), r in sorted(obs["switching"].items()):
        x = b if a == REFERENCE else a
        direction = "there and back" if a == REFERENCE else "back and forth"
        for item in r["lost"]:
            add("switch_back", "manual", x, item,
                f"{a} -> {b} -> {a}", "lost")
        add("inherits", "manual", x, f"{a} -> {b}", direction,
            r["inherited"])

    for key in ("run_types", "prefs_style"):
        check = "run_type" if key == "run_types" else "prefs_style"
        for mode in MODES:
            ref = obs[key].get((mode, REFERENCE))
            for code in codes:
                got = obs[key].get((mode, code))
                if code == REFERENCE or got == ref:
                    continue
                if isinstance(got, dict):
                    for rt in got:
                        if got[rt] != (ref or {}).get(rt):
                            add(check, mode, code, rt, "state", got[rt],
                                (ref or {}).get(rt))
                else:
                    add(check, mode, code, "label style", "state", got, ref)
    return rows


# ---------------------------------------------------------------------------
# The allow-list
# ---------------------------------------------------------------------------

def load_allowlist(path: Path = ALLOWLIST) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _key(row: dict) -> tuple:
    return (row["check"], row.get("mode", ""), row["instrument"],
            row["item"], row["aspect"])


def expand(allow: dict, codes: list[str]) -> dict[tuple, dict]:
    """{key: entry} for every (instrument) an entry names. ``"*"`` is every
    instrument discovered. The shared list turns into the expected
    ``inherits`` rows: an entry for an ``inherits`` row lists the fields
    beyond the shared ones."""
    out: dict[tuple, dict] = {}
    for status in ("intended", "known_to_review"):
        for e in allow.get(status, []):
            inst = e["instrument"]
            members = codes if inst == "*" else (
                inst if isinstance(inst, list) else [inst])
            items = e["item"] if isinstance(e["item"], list) else [e["item"]]
            for c in members:
                for item in items:
                    k = (e["check"], e.get("mode", ""), c, item, e["aspect"])
                    out[k] = {**e, "_status": status}
    return out


def shared_fields(allow: dict) -> set[str]:
    return set((allow.get("shared") or {}).get("fields", []))


def compare(rows: list[dict], allow: dict, codes: list[str]):
    """(unexplained rows, stale entries, mismatched rows)."""
    allowed = expand(allow, codes)
    shared = shared_fields(allow)
    unexplained, mismatched = [], []
    used = set()
    for r in rows:
        if r["check"] == "inherits":
            extra = sorted(set(r["expected"]) - shared)
            if not extra:
                continue
            r = {**r, "expected": extra}
        k = _key(r)
        e = allowed.get(k)
        if e is None:
            unexplained.append(r)
            continue
        used.add(k)
        if not _same_expected(e.get("expected"), r["expected"]):
            mismatched.append({**r, "allow_list_says": e.get("expected")})
    stale = [{"check": k[0], "mode": k[1], "instrument": k[2], "item": k[3],
              "aspect": k[4], "expected": e.get("expected")}
             for k, e in sorted(allowed.items(), key=lambda kv: str(kv[0]))
             if k not in used and k[2] in codes]
    return unexplained, stale, mismatched


def _same_expected(a, b) -> bool:
    if isinstance(a, list) and isinstance(b, list):
        return sorted(map(str, a)) == sorted(map(str, b))
    return _same(a, b)


def as_entries(rows: list[dict]) -> str:
    """The rows as allow-list entries, ready to paste (reason to be written)."""
    out = []
    for r in rows:
        e = {k: r[k] for k in ("check", "mode", "instrument", "item",
                               "aspect", "expected")}
        e["reason"] = "WRITE ONE PLAIN SENTENCE"
        out.append(e)
    return json.dumps(out, indent=1, ensure_ascii=False)


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", nargs="*", help="instrument codes to check "
                    "(the reference is always included)")
    ap.add_argument("--all", action="store_true",
                    help="print every difference, not only the unexplained")
    args = ap.parse_args(argv)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    with tempfile.TemporaryDirectory(prefix="chromiq-parity-") as tmp:
        os.environ.setdefault("CHROMIQ_SETTINGS_FILE",
                              str(Path(tmp) / "app.ini"))
        os.environ.setdefault("CHROMIQ_PRESETS_DIR", str(Path(tmp) / "presets"))
        os.environ.setdefault("CHROMIQ_LOG_DIR", str(Path(tmp) / "logs"))
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        app.setStyle("Fusion")
        with betas_on():
            obs = observe(Path(tmp) / "bench", args.only,
                          log=lambda m: print("..", m, file=sys.stderr))
        rows = differences(obs)
        allow = load_allowlist() if ALLOWLIST.exists() else {}
        un, stale, mis = compare(rows, allow, obs["instruments"])
        print(f"instruments: {', '.join(obs['instruments'])} "
              f"(reference {REFERENCE})")
        print(f"differences observed: {len(rows)}; not on the allow-list: "
              f"{len(un)}; allow-list entries that no longer match: "
              f"{len(stale) + len(mis)}")
        if obs.get("questions"):
            print(f"windows that asked a question during the walks "
                  f"(answered Cancel): {len(obs['questions'])}")
            for q in sorted(set(obs["questions"])):
                print("  ", " | ".join(map(str, q)))
        if args.all:
            print(as_entries(rows))
        elif un:
            print("\nNOT ON THE ALLOW-LIST (paste into "
                  f"{ALLOWLIST.relative_to(REPO)} with a reason):")
            print(as_entries(un))
        if stale or mis:
            print("\nALLOW-LIST ENTRIES THAT NO LONGER MATCH:")
            print(json.dumps(stale + mis, indent=1, ensure_ascii=False))
        return 1 if (un or stale or mis) else 0


if __name__ == "__main__":
    sys.exit(main())
