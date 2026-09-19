"""#182, beta 23: the demo presets built to fail ONE verification metric each.

Knut, 2026-09-19:

    *"the demo package project must create a set of demo chart presets that are
    built to fail the metrics used during a verification. One test-preset made
    to fail one metric […] The agents testing shall use these presets in tests
    to confirm they are working. […] a user can place the presets in the
    '…/Library/Preferences/ChromIQ/presets/Create Chart' folder (on mac), and
    restart the app. The demo presets shall then be visible in the preset
    pulldown, and when opening the 'Which presets can be verified?' window."*

**WHY THESE PRESETS HAD TO EXIST.** Measured on beta 22 and written into that
round's own proof: *"Every built-in preset answers every patch-based row."* So
the window's detection had 177 charts to look at and not one of them could make
it say anything. These fourteen can, one fault each, and these guards are what
stops a detection from quietly going dead.

Everything here is driven through the app's own sequence: the presets are
COPIED INTO THE PRESET FOLDER the way a user would copy them, a real
``TabChart`` is built in Manual mode, the real button is clicked, the real
handler opens the real window, and each preset is selected in the real tree so
the real detail pane is what gets read.

The claims live in ``scripts/make_verification_preset_demos.DEMOS`` beside the
chart that makes them, and ``test_every_demo_fails_exactly_what_it_claims``
refuses to let the two drift: a chart edited into failing a second row turns
this file red rather than shipping a preset whose name is a lie.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt                                        # noqa: E402
from PyQt6.QtWidgets import QApplication                           # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from core.argyll_runner import ArgyllRunner                        # noqa: E402
from core.file_manager import FileManager                          # noqa: E402
from core.preset_store import tab_dir                              # noqa: E402
from core.settings import AppSettings                              # noqa: E402
from ui.dialogs import preset_verification_dialog as PVD           # noqa: E402
from ui.tabs.tab_chart import TabChart                             # noqa: E402
from workflow import measurement_report as MR                      # noqa: E402
from workflow import preset_eligibility as PE                      # noqa: E402

import make_verification_preset_demos as GEN                       # noqa: E402

#: The strictest combination ChromIQ offers: all sixteen computable rows are
#: asked, so every reason a chart can give has somewhere to appear. A demo that
#: fails a row nobody asked about would go unnoticed on any softer pair.
STRICT = (MR.REPORT_TYPE_FULL, "custom_iso_12647_7")

#: The three rows NO preset chart can answer, on any patch set: a colorimetric
#: reference is written only beside a chart built FROM PROFILE GAMUT. They are
#: the constant background every demo carries and no demo claims.
CONSTANT = MR.REASON_NEEDS_REFERENCE_FILE


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def installed(qapp, tmp_path_factory):
    """The presets, installed THE WAY A USER INSTALLS THEM.

    The generator writes the downloadable folder; this copies its contents into
    the Create Chart preset folder and nothing else happens. No app code is
    asked to import anything, because a user has no such door: he drops the
    files in and restarts, and the restart is what building a fresh
    ``TabChart`` below stands in for.
    """
    pack = tmp_path_factory.mktemp("pack") / GEN.FOLDER
    GEN.build(pack)
    dest = tab_dir("create_chart")
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for src in sorted(pack.iterdir()):
        if src.suffix not in (".json", ".ti1"):
            continue
        shutil.copy2(src, dest / src.name)
        copied.append(dest / src.name)
    PE.clear_cache()
    yield pack
    for p in copied:
        p.unlink(missing_ok=True)
    PE.clear_cache()


@pytest.fixture(scope="module")
def dialog(qapp, installed):
    """The window, opened by a real click on the real button of a real tab."""
    s = AppSettings()
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    tab.show()
    qapp.processEvents()
    tab._manual_btn.click()
    qapp.processEvents()

    opened: list = []
    real_exec = PVD.PresetVerificationDialog.exec

    def _no_block(self):
        opened.append(self)
        return 0

    PVD.PresetVerificationDialog.exec = _no_block
    try:
        tab._preset_verify_btn.click()
        qapp.processEvents()
    finally:
        PVD.PresetVerificationDialog.exec = real_exec
    assert opened, "clicking the real button opened no window"
    dlg = opened[0]
    _choose(dlg, *STRICT)
    qapp.processEvents()
    yield dlg
    dlg.close()
    tab.close()
    tab.deleteLater()
    qapp.processEvents()


def _choose(dlg, type_id: str, set_id: str) -> None:
    """Pick a report type and a limit set through the window's own combos."""
    dlg._type_combo.setCurrentIndex(dlg._type_combo.findData(type_id))
    dlg._set_combo.setCurrentIndex(dlg._set_combo.findData(set_id))


def _item_for(dlg, label: str):
    """The tree item for one preset, found the way a reader finds it."""
    tree = dlg._tree
    for i in range(tree.topLevelItemCount()):
        head = tree.topLevelItem(i)
        for j in range(head.childCount()):
            child = head.child(j)
            row = child.data(0, Qt.ItemDataRole.UserRole)
            if row is not None and row.label == label:
                return head, child, row
    return None, None, None


def _detail_text(dlg, item) -> "list[str]":
    """Select the preset in the real tree and read the real detail pane."""
    dlg._tree.setCurrentItem(item)
    QApplication.instance().processEvents()
    out = []
    for i in range(dlg._detail_layout.count()):
        w = dlg._detail_layout.itemAt(i).widget()
        if w is not None and hasattr(w, "text"):
            out.append(w.text())
    return out


# ---------------------------------------------------------------------------
# 1. they arrive, the way a user's own presets arrive
# ---------------------------------------------------------------------------
def test_every_demo_preset_reaches_the_window(dialog):
    """Knut: *"The demo presets shall then be visible in the preset pulldown,
    and when opening the window."* The window half, on the real list."""
    labels = {r.label for r in dialog._rows}
    missing = [d.name for d in GEN.DEMOS if d.name not in labels]
    assert not missing, missing
    for d in GEN.DEMOS:
        _head, item, _row = _item_for(dialog, d.name)
        assert item is not None, f"{d.name} is not in the tree"


def test_the_demos_are_grouped_as_the_users_own_presets(dialog):
    """They are user presets, not built-ins, and the window must say so: a
    demo that arrived in an instrument group would be claiming to ship with
    ChromIQ."""
    for d in GEN.DEMOS:
        head, _item, row = _item_for(dialog, d.name)
        assert not row.builtin, d.name
        assert head.text(0) == "Custom presets", (d.name, head.text(0))


def test_every_demo_preset_reaches_the_dropdown(qapp, installed):
    """The pulldown half of the same sentence, on a freshly built tab, which
    is what a restart gives the user."""
    s = AppSettings()
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    try:
        tab.show()
        qapp.processEvents()
        tab._manual_btn.click()
        qapp.processEvents()
        combo = tab._preset_combo
        listed = {combo.itemText(i) for i in range(combo.count())}
        missing = [d.name for d in GEN.DEMOS
                   if not any(d.name in t for t in listed)]
        assert not missing, missing
    finally:
        tab.close()
        tab.deleteLater()
        qapp.processEvents()


# ---------------------------------------------------------------------------
# 2. each one fails exactly what it claims, and the window says which
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("demo", [d for d in GEN.DEMOS if not d.no_chart
                                  and not d.corrupt],
                         ids=lambda d: f"{d.n:02d}")
def test_every_demo_fails_exactly_what_it_claims(dialog, demo):
    """The window's own assessment, on the strictest pair, against the claim
    the preset's name makes.

    ``needs_reference_file`` is excluded because it is not a claim anybody can
    make or avoid: it is on all three reference rows of all 177 built-ins too.
    Everything else the window withholds has to be in the demo's own list.
    """
    _head, item, row = _item_for(dialog, demo.name)
    assert item is not None, demo.name
    got = sorted({why for _rid, why in row.assessment.missing
                  if why != CONSTANT})
    want = sorted({demo.reason} | set(demo.also)) if demo.reason else []
    assert got == want, (demo.name, got, want)


@pytest.mark.parametrize("demo", [d for d in GEN.DEMOS if d.reason],
                         ids=lambda d: f"{d.n:02d}")
def test_the_window_says_what_is_missing_in_its_own_words(dialog, demo):
    """Knut asked the window to *"report what is wrong/missing"*. The detail
    pane must carry the sentence for the reason, and the metric's own remedy
    beside it, for the rows that really are short."""
    _head, item, row = _item_for(dialog, demo.name)
    shown = _detail_text(dialog, item)
    sentence = PVD.reason_line(demo.reason)
    assert sentence in shown, (demo.name, sentence, shown)
    short = [rid for rid, why in row.assessment.missing if why == demo.reason]
    assert short, demo.name
    for rid in short:
        assert "✕  " + PE.row_label(rid) in shown, (demo.name, rid)
        remedy = PE.row_remedy(rid)
        if remedy:
            assert remedy in shown, (demo.name, rid, remedy)


def test_the_control_preset_answers_every_row_its_patches_decide(dialog):
    """Demo 00 is the control, and a control that quietly fails something
    makes every other row in this file unreadable."""
    _head, item, row = _item_for(dialog, GEN.DEMOS[0].name)
    assert row.assessment.checked
    assert not row.assessment.patch_shortfalls, row.assessment.missing
    # …and on the everyday pair it answers everything that is asked at all.
    _choose(dialog, MR.REPORT_TYPE_FULL, "chromiq_default")
    QApplication.instance().processEvents()
    _head, item, row = _item_for(dialog, GEN.DEMOS[0].name)
    assert row.assessment.answers_everything, row.assessment.missing
    _choose(dialog, *STRICT)
    QApplication.instance().processEvents()


def test_the_short_strip_demo_loses_three_rows_and_the_shorter_one_loses_one(
        dialog):
    """Demos 09 and 10 carry the SAME reason code and are not the same fault:
    five declared patches withhold all three control-strip rows, twelve
    withhold only the 95th percentile. A window that collapsed them would
    still pass every other assertion in this file."""
    _h, _i, five = _item_for(dialog, GEN.DEMOS[9].name)
    _h, _i, twelve = _item_for(dialog, GEN.DEMOS[10].name)
    code = MR.REASON_CONTROL_STRIP_TOO_SMALL
    hit5 = {rid for rid, why in five.assessment.missing if why == code}
    hit12 = {rid for rid, why in twelve.assessment.missing if why == code}
    assert hit5 == {"control_strip_de00_avg", "control_strip_de00_max",
                    "control_strip_de00_p95"}, hit5
    assert hit12 == {"control_strip_de00_p95"}, hit12


def test_the_smallest_chart_cannot_fail_alone_and_says_so(dialog):
    """Demo 11's three reasons are arithmetic, not sloppiness, and the claim
    the package makes about it has to stay true: under twenty patches there
    cannot be twenty in the top chroma quarter, nor twenty on a control strip.
    """
    demo = GEN.DEMOS[11]
    assert demo.reason == MR.REASON_SMALL_SAMPLE
    assert set(demo.also) == {MR.REASON_TOO_FEW_OUTER_PATCHES,
                              MR.REASON_CONTROL_STRIP_TOO_SMALL}
    _head, _item, row = _item_for(dialog, demo.name)
    n = row.patches
    assert n < 20, n
    assert n * 0.25 < 20 and n < MR.CONTROL_STRIP_P95_MIN


# ---------------------------------------------------------------------------
# 3. the two presets that are not metrics at all
# ---------------------------------------------------------------------------
def test_a_preset_with_no_patch_set_is_listed_and_told_which_tick_box(dialog):
    demo = next(d for d in GEN.DEMOS if d.no_chart)
    _head, item, row = _item_for(dialog, demo.name)
    assert row.chart is None
    assert not row.assessment.checked
    shown = _detail_text(dialog, item)
    assert any("attach its .ti1" in t for t in shown), shown
    assert not any(t.startswith("0 patch") or " 0 page" in t for t in shown)


def test_a_preset_whose_chart_cannot_be_read_says_so(dialog):
    demo = next(d for d in GEN.DEMOS if d.corrupt)
    _head, item, row = _item_for(dialog, demo.name)
    assert row.chart is not None, "the unreadable .ti1 was not even found"
    assert not row.assessment.checked
    shown = _detail_text(dialog, item)
    assert any("could not read" in t for t in shown), shown


# ---------------------------------------------------------------------------
# 4. the package's arithmetic about itself
# ---------------------------------------------------------------------------
def test_the_package_accounts_for_every_reason_the_window_can_show(dialog):
    """Ten covered plus four named unreachable must be the window's fourteen.
    A new reason code lands here before it lands in a release with no demo and
    no explanation."""
    covered = {d.reason for d in GEN.DEMOS if d.reason}
    covered |= {r for d in GEN.DEMOS for r in d.also}
    unreachable = set(GEN.UNREACHABLE)
    assert not (covered & unreachable), covered & unreachable
    assert covered | unreachable == PE.classified_reasons(), (
        "unaccounted: "
        f"{sorted(PE.classified_reasons() - covered - unreachable)}")


def test_the_unreachable_four_really_are_unreachable_here(dialog):
    """Not taken on trust: no demo, and no built-in, ever shows one of them,
    with the single exception of the reference code that every chart shows."""
    seen = set()
    for row in dialog._rows:
        seen |= {why for _rid, why in row.assessment.missing}
    for code in GEN.UNREACHABLE:
        if code == CONSTANT:
            assert code in seen, "every preset should read needs_reference_file"
        else:
            assert code not in seen, code


def test_each_demo_carries_its_own_patch_set(dialog, installed):
    """A preset whose .ti1 did not travel with it is a preset that proves
    nothing, and the pair is what the README tells a user to copy."""
    from core.preset_store import sidecar_path
    for d in GEN.DEMOS:
        sc = sidecar_path("create_chart", d.name, ".ti1")
        assert sc.is_file() is (not d.no_chart), d.name


def test_the_readme_names_both_preset_folders_and_the_restart(installed):
    """The download is useless without it: Knut named the macOS path himself
    and a Windows user needs the other one."""
    text = (installed / "README.txt").read_text(encoding="utf-8")
    assert "Library/Preferences/ChromIQ/presets/Create Chart" in text
    assert "%APPDATA%\\ChromIQ\\presets\\Create Chart" in text
    assert "RESTART" in text.upper()
    for d in GEN.DEMOS:
        assert d.name in text, d.name


def test_no_demo_name_or_blurb_carries_an_em_dash():
    """The house rule. These strings reach the dropdown and the README."""
    for d in GEN.DEMOS:
        assert "—" not in d.name, d.name
        assert "—" not in d.blurb, d.name
    assert "—" not in GEN.readme()


# ---------------------------------------------------------------------------
# 5. and they ship
# ---------------------------------------------------------------------------
def test_a_pack_without_the_preset_folder_is_incomplete(tmp_path):
    """Knut asked for them IN the downloadable package, and a pack has been
    published missing part of itself before (B8-393). ``verify_pack`` is the
    release step's own check, so the folder is added to what it demands rather
    than to a list somebody reads."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import make_report_limit_demos as PACK

    pack = tmp_path / "ChromIQ-Report-Limit-Demos"
    pack.mkdir()
    for name, _plans in PACK.PROJECTS:
        (pack / name).mkdir()
    (pack / "README.txt").write_text("x", encoding="utf-8")
    (pack / "intended-vs-actual.json").write_text("[]", encoding="utf-8")
    gaps = PACK.verify_pack(pack)
    assert f"file missing: {GEN.FOLDER}" in gaps, gaps

    GEN.build(pack / GEN.FOLDER)
    gaps = PACK.verify_pack(pack)
    assert not [g for g in gaps if GEN.FOLDER in g], gaps


def test_the_pack_readme_sends_the_user_to_the_right_folder(tmp_path):
    """The section the pack's own README grew, checked on the text it writes:
    a download whose README does not say where the files go is a download
    nobody can use."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import make_report_limit_demos as PACK

    text = PACK.readme([], [], PACK.coverage(tmp_path, []), tmp_path)
    assert GEN.FOLDER in text
    assert "~/Library/Preferences/ChromIQ/presets/Create Chart" in text
    assert "%APPDATA%\\ChromIQ\\presets\\Create Chart" in text
    assert "restart ChromIQ" in text
