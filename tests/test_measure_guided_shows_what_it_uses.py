"""Guided uses only what it shows, and shows only what it uses (#160).

Four faults grew from one root — Guided and Manual were built from two
near-duplicate option tables:

* **D1** the Guided "patch by patch" box was hidden but still read, so a stored
  preference put ``-p`` on every Guided measurement invisibly;
* **D2** five hidden Guided rows were still collected — ticking them in Manual
  and measuring in Guided produced ``-H -F 5 -T 0.7 -l -L -A N``;
* **D3** ``-n`` existed only in Manual, so the Guided↔Manual mirror dropped it;
* **D4** *Save as Defaults* wrote the hidden options into the GLOBAL defaults, so
  one Manual visit baked ``-H -l -L -A`` into every future target on the machine.

The fix is structural: Manual's table is now the single definition and Guided is
built from it, filtered by :data:`GUIDED_CHARTREAD_KEYS`. These tests pin that
the fault family cannot come back — most of them would fail if someone
re-introduced a second option table.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from ui.tabs.tab_measure import GUIDED_CHARTREAD_KEYS  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    t = TabMeasure(ArgyllRunner(s), s)
    t._ti1_path = tmp_path / "chart.ti1"
    return t


def _tick_everything(tab):
    for o in tab._m_chartread_opts:
        if o.checkbox is not None:
            o.checkbox.setChecked(True)


# ---------------------------------------------------------------------------
# One table (the structural fix)
# ---------------------------------------------------------------------------

def test_guided_options_are_a_subset_of_manuals(tab):
    """Both panels come from one definition, so no key can exist in one and not
    the other — which is what let ``-n`` fall through the mirror (D3)."""
    g = {o.key for o in tab._chartread_opts}
    m = {o.key for o in tab._m_chartread_opts}
    assert g <= m, f"Guided has options Manual does not: {sorted(g - m)}"
    assert g == GUIDED_CHARTREAD_KEYS


def test_guided_builds_only_what_it_offers(tab):
    """D2: ticking everything in Manual must not leak into a Guided read."""
    _tick_everything(tab)
    manual = tab._collect_manual().extra_args
    guided = tab._collect_guided().extra_args
    for flag in ("-H", "-F", "-l", "-L", "-n", "-A"):
        assert flag in manual, f"Manual lost {flag} — it must offer everything"
        assert flag not in guided, (
            f"Guided built {flag}, an option it does not show — this is D2")


def test_the_one_option_guided_offers_still_reaches_the_command_line(tab):
    """The counterweight, and the reason this is not filtered on isVisible():
    on a tab that has not been shown, even this row reports invisible, so a
    visibility test would silently drop ``-T``."""
    opt = next(o for o in tab._chartread_opts if o.key == "tolerance")
    opt.checkbox.setChecked(True)
    opt.widget.setValue(0.7)
    assert "-T" in tab._collect_guided().extra_args


def test_no_option_is_filtered_on_runtime_visibility(tab):
    """A guard on the mechanism, not just the outcome: `isVisible()` is False
    for every row on an unshown tab, so any implementation that consults it is
    wrong even when the result happens to look right."""
    import inspect
    src = inspect.getsource(tab._collect_guided.__func__)
    assert "isVisible" not in src and "isHidden" not in src, (
        "Guided is filtering options on runtime visibility — on an unshown tab "
        "that drops -T")


# ---------------------------------------------------------------------------
# D1 — the invisible tick box
# ---------------------------------------------------------------------------

def test_guided_patch_by_patch_is_visible(qapp, tmp_path):
    """It sets a flag, so the user must be able to see and change it. A stored
    preference used to switch every Guided measurement to patch-by-patch with
    no control on screen — the same fault as the -N incident in beta.148."""
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s2.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("measure_patch_by_patch", True)          # the preference that bit
    t = TabMeasure(ArgyllRunner(s), s)
    t.show()
    qapp.processEvents()
    assert t._pbp_cb.isVisible(), "the box that puts -p on the command line is hidden"
    assert t._pbp_cb.isChecked()
    t.close()


def test_guided_still_deliberately_never_sends_skip_calibration(tab):
    """The one asymmetry that is intended: Guided does not offer -N, and hard-
    codes it off, because a stored value once ran every guided measurement
    uncalibrated. Manual still offers it."""
    tab._nocal_cb.setChecked(True)          # even if something set it
    assert tab._collect_guided().disable_initial_cal is False
    tab._m_nocal_cb.setChecked(True)
    assert tab._collect_manual().disable_initial_cal is True


# ---------------------------------------------------------------------------
# D4 — Save as Defaults
# ---------------------------------------------------------------------------

def test_save_as_defaults_cannot_bake_in_options_guided_does_not_offer(tab):
    """One Manual visit plus one Save as Defaults used to write -H -l -L -A into
    the global defaults, for every future target on the machine."""
    _tick_everything(tab)
    tab._on_save_defaults()
    for key in ("highres", "save_lab", "save_lab_and_xyz", "xrga",
                "filter", "no_spectral"):
        stored = tab._settings.get(f"measure_{key}_enabled", None)
        assert not stored, (
            f"{key} reached the global defaults from Guided's Save as Defaults")


# ---------------------------------------------------------------------------
# The information box
# ---------------------------------------------------------------------------

def test_the_info_box_names_exactly_what_guided_fixes(tab):
    """Derived from the one table at run time, so it cannot drift from what
    Guided actually builds — which is the whole point of showing it."""
    text = tab._guided_fixed_lbl.text()
    assert text, "Guided says nothing about the options it fixes"
    for o in tab._m_chartread_opts:
        if o.key in GUIDED_CHARTREAD_KEYS:
            assert o.label not in text, f"{o.key} is offered, not fixed"
        else:
            assert o.label in text, f"{o.key} is fixed but not named"
    assert "MANUAL" in text, "it must say where to go for the rest"


# ---------------------------------------------------------------------------
# Knut's linking rule, as he stated it on 2026-08-21
# ---------------------------------------------------------------------------

def test_a_shared_visible_option_follows_between_the_modes(tab, qapp):
    """His beta.138 rule, which he confirmed covers *shared and visible*
    parameters: patch-by-patch is now offered in both modules, so the two must
    follow each other."""
    tab._pbp_cb.setChecked(False)
    tab._m_pbp_cb.setChecked(False)
    qapp.processEvents()

    tab._m_pbp_cb.setChecked(True)
    qapp.processEvents()
    assert tab._pbp_cb.isChecked(), "Manual did not carry to Guided"

    tab._pbp_cb.setChecked(False)
    qapp.processEvents()
    assert not tab._m_pbp_cb.isChecked(), "Guided did not carry to Manual"


def test_a_guided_hard_coded_default_is_never_overwritten_from_manual(tab, qapp):
    """The other half of his ruling, and the more important one: a value Guided
    fixes must NOT be linked, or Manual could silently change what Guided does.

    ``-N`` is the case that exists today — Guided hard-codes it off because a
    stored value once ran every guided measurement uncalibrated.
    """
    tab._m_nocal_cb.setChecked(True)
    qapp.processEvents()
    assert tab._collect_guided().disable_initial_cal is False
    assert tab._collect_manual().disable_initial_cal is True

    # …and the six options Manual keeps to itself cannot reach Guided either.
    for o in tab._m_chartread_opts:
        if o.checkbox is not None:
            o.checkbox.setChecked(True)
    qapp.processEvents()
    assert tab._collect_guided().extra_args.strip() in ("", "-T 0.7"), (
        "a Manual-only option reached Guided's command line")
