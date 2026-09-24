"""#182, beta 29: a user preset's page count is DERIVED, not written off as 0.

Knut opened "Which presets can be used for verification" on the demo pack that
exists to exercise that window, selected *"Verify R11 FAIL, 12 candidates,
every one 2.1 from the nearest face"*, and the detail pane said:

    *"ChromIQ cannot tell how many pages this preset lays out until its chart
    is generated, so it is not marked as made for verification."*

Thirteen FAIL/PASS pairs built FOR this check, and the check was failing on
every one of them. The sentence was TRUE of the code and FALSE of the app:
``ui.tabs.tab_chart.verification_preset_rows`` hard-coded ``pages=0`` for a
user preset, while the Create Chart tab answers exactly that question on every
Generate click out of the measured per-sheet table in ``data.patch_db``. So the
CHECK was fixed and the sentence left alone.

These guards operate what a user touches: the REAL demo presets, written by the
script that ships them, into a sandboxed ``CHROMIQ_PRESETS_DIR``, read back
through the tab's own ``verification_preset_rows``. Nothing here constructs a
``PresetRow`` or reads a widget's text.

The fallback is guarded too, and it matters as much as the fix: where the
measured table cannot answer (an unsupported patch scale, a layout-engine
recipe) the count must still be 0, so the honest sentence above still shows.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                            # noqa: E402

from core.settings import AppSettings                               # noqa: E402
from workflow import preset_eligibility as PE                       # noqa: E402

_REPO = Path(__file__).resolve().parents[1]

#: The preset Knut named, and its partner. The FAIL half deliberately misses
#: ONE requirement (its surface candidates sit 2.1 device units off the nearest
#: cube face, where the rule is 2.0), so it is the PASS half that must carry
#: the star once the page count is right.
#: From K15 the names carried "[judge with Custom ISO 12647-7]", because the
#: window opened on ChromIQ default, which asks nothing about the surface of
#: the device cube. Since B8-974 it opens on "All metrics", which asks it, so
#: the generator adds no tag (`make_verification_preset_demos.where_label`).
R11_FAIL = ("Verify R11 FAIL, 12 candidates, "
            "every one 2.1 from the nearest face")
R11_PASS = ("Verify R11 PASS, the same 12, "
            "every one exactly 2.0 from the nearest face")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _demo_module():
    """The shipped generator, imported from its own path (scripts/ is not a
    package, and this test must build the SAME files a user downloads)."""
    path = _REPO / "scripts" / "make_verification_preset_demos.py"
    spec = importlib.util.spec_from_file_location(
        "_chromiq_verification_preset_demos", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _rows(sandbox: Path):
    """Every row the window is handed, with the presets directory sandboxed.

    Imported late and re-read on each call: ``presets_dir()`` reads the
    environment at call time, so the variable has to be set first.
    """
    from ui.tabs.tab_chart import verification_preset_rows
    assert os.environ["CHROMIQ_PRESETS_DIR"] == str(sandbox)
    PE.clear_cache()
    return verification_preset_rows(AppSettings())


@pytest.fixture
def demo_pack(tmp_path, monkeypatch, qapp):
    """The real demo pack on disk, in a presets directory of its own."""
    sandbox = tmp_path / "presets"
    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(sandbox))
    from core.preset_store import tab_dir
    folder = tab_dir("create_chart")
    folder.mkdir(parents=True, exist_ok=True)
    _demo_module().build(folder)
    assert (folder / (R11_FAIL + ".ti1")).is_file(), \
        "the demo generator did not write the preset this guard is about"
    yield sandbox
    PE.clear_cache()


# ---------------------------------------------------------------------------
# 1. the fault Knut reported
# ---------------------------------------------------------------------------
def test_the_r11_preset_is_counted_at_one_page(demo_pack):
    """The R11 pair is an i1Pro / A4 / -L chart of 78 patches, and i1Pro on A4
    holds 504 of them. One page, and the window may say so."""
    rows = {r.label: r for r in _rows(demo_pack) if not r.builtin}
    fail, ok = rows[R11_FAIL], rows[R11_PASS]
    assert fail.patches == 78 and ok.patches == 78
    assert fail.pages == 1, \
        "the preset Knut selected is still counted as an unknown number of pages"
    assert ok.pages == 1


def test_the_page_count_is_what_decides_the_star(demo_pack):
    """And the count reaches the star: the PASS half of the pair is marked
    made-for-verification, which it could never be while ``pages`` was 0
    (``made_for_verification`` refuses ``pages < 1`` outright)."""
    rows = {r.label: r for r in _rows(demo_pack) if not r.builtin}
    ok = rows[R11_PASS]
    assert PE.made_for_verification(ok.chart, ok.patches, ok.pages,
                                    relayoutable=ok.relayoutable), \
        "the preset built to pass R11 is still not marked for verification"
    # The FAIL half stays unstarred, and now for the RIGHT reason: it is one
    # notch outside the surface-patch rule, not a preset of unknown length.
    fail = rows[R11_FAIL]
    assert fail.pages == 1
    assert not PE.made_for_verification(fail.chart, fail.patches, fail.pages,
                                        relayoutable=fail.relayoutable)


def test_every_demo_preset_that_ships_a_chart_is_counted(demo_pack):
    """Not one of them, all of them: the whole pack was built one page each,
    and only the two that ship no readable patch set stay at 0."""
    user = [r for r in _rows(demo_pack) if not r.builtin]
    assert len(user) >= 30, user
    counted = [r for r in user if r.patches]
    uncounted = [r for r in user if not r.patches]
    assert counted and all(r.pages == 1 for r in counted), \
        [(r.label, r.pages) for r in counted if r.pages != 1]
    assert all(r.pages == 0 for r in uncounted)


# ---------------------------------------------------------------------------
# 2. the fallback, which must be exactly what it was
# ---------------------------------------------------------------------------
def _rewrite(sandbox: Path, name: str, **changes) -> None:
    """Change one stored value in a preset on disk, as saving it again would."""
    from core.preset_store import tab_dir
    path = tab_dir("create_chart") / (name + ".json")
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["data"].update(changes)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def test_a_combination_the_table_never_measured_is_still_unknown(demo_pack):
    """A patch scale of 1.25 is not in the measured table and cannot be
    binary-searched from a dialog, so the count stays 0 and the window keeps
    saying so. This is the branch the honest sentence exists for."""
    _rewrite(demo_pack, R11_FAIL, **{"printtarg_-a": 1.25})
    row = next(r for r in _rows(demo_pack) if r.label == R11_FAIL)
    assert row.patches == 78
    assert row.pages == 0


def test_a_layout_engine_recipe_is_still_unknown(demo_pack):
    """The ChromIQ layout engine places patches by its own geometry, which the
    printtarg tables say nothing about."""
    _rewrite(demo_pack, R11_FAIL, layout_recipe={"paper": "A4"})
    row = next(r for r in _rows(demo_pack) if r.label == R11_FAIL)
    assert row.pages == 0


def test_an_auto_patch_preset_is_taken_at_its_word(demo_pack):
    """With "Auto" ticked the Pages spin box is the person's own answer (it is
    the only state in which it is enabled), so it is used as stored."""
    _rewrite(demo_pack, R11_FAIL, auto_patches=True, pages=3)
    row = next(r for r in _rows(demo_pack) if r.label == R11_FAIL)
    assert row.pages == 3


def test_the_disabled_pages_box_is_not_believed(demo_pack):
    """…and with Auto OFF it is a greyed-out default that must not be read as
    an answer. Storing 7 pages beside a 78-patch chart changes nothing."""
    _rewrite(demo_pack, R11_FAIL, auto_patches=False, pages=7)
    row = next(r for r in _rows(demo_pack) if r.label == R11_FAIL)
    assert row.pages == 1
