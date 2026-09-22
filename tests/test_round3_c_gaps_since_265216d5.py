"""Round 3-C (2026-09-22): the mutants of 265216d5..d68d7026 that no guard
killed, each given the test it was missing.

Every test here was run GREEN on d68d7026 and RED on the mutant its docstring
names, applied exactly as described, with one stated exception (the leftover
re-stamp, whose mutant is equivalent). Proof, mutant by mutant:
~/Desktop/ChromIQ-beta36-proof/round3-C-guards-and-gate/REPORT.md.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_an_untyped_saved_verification_report_is_labelled_with_its_runs_type(
        tmp_path, qapp):
    """Round 2B #1's other half. A saved report that records NO type is
    labelled with what the page draws for it, and for a dated verification
    the page follows the RUN (§10). The existing guard only covered a
    profiling sheet, where the run does not matter (its type is always the
    Printing record).

    MUTANT D04: pass `None` for the run to `report_type_default_for` in
    `_type_a_file_renders_as`, and a Grey-and-tone run's untyped report is
    labelled Full colour check.
    """
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import REPORT_TYPE_GREY
    from workflow.run_compliance import set_run_report_type
    s, _fm, _ctl, run = _verify_env(tmp_path)
    set_run_report_type(run, REPORT_TYPE_GREY)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    try:
        r = dict(dlg._report, _origin_dir=str(v.dir),
                 ti3=v.measurement_ti3.name)
        rep = {k: val for k, val in r.items() if k != "report_type"}
        assert dlg._type_a_file_renders_as(rep, r) == REPORT_TYPE_GREY
    finally:
        dlg.close()


@pytest.mark.parametrize("how", ["just written", "picked in a new window"])
def test_the_page_stops_being_the_saved_document_when_its_list_changes(
        tmp_path, qapp, how):
    """Round 2B #6: adding another measurement redraws the page at once, so
    it is no longer the saved document and must not print that document's
    "Created:" time (nor offer its PDF name). Nothing guarded it.

    Two ways onto the document, because the list it was drawn from is
    recorded at three sites and each way reaches different ones: the press
    that wrote it (`_write_the_document`) and a later pick
    (`_adopt_visible_document` / `_apply_document`).

    MUTANTS KILLED: D08 (drop the `_doc_sources` clause from `speaks` in
    `_note_which_document_the_page_is`) and D09 (`_source_signature` returns
    a constant) on both paths; D12 (drop the `_apply_document` assignment) on
    "picked in a new window". NOT killed, measured, and redundant rather than
    missing: D10 (the assignment after a press) and D11 (the
    `_adopt_visible_document` one), because on every path measured another
    of the three sites records the same list before the page is drawn.
    """
    from tests.test_a_generated_report_is_one_document import _messy_project
    from tests.test_generate_report_asks_what_to_do import (
        _a_real_document, _pick_key, _window)
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, _run, vs = _messy_project(tmp_path, dates=2)
    loose = tmp_path / "Downloads" / "loose.ti3"
    loose.parent.mkdir()
    loose.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
        if how == "picked in a new window":
            dlg.close()
            dlg = _window(s, vs[-1].measurement_ti3, qapp)
            dlg._saved_combo.setCurrentIndex(0)
            qapp.processEvents()
            _pick_key(dlg, key, qapp)
        created = str(dlg._doc_created or "")
        assert created, "the picked document carries no creation stamp"
        assert dlg._page_doc_created == created, (
            "the page does not speak for the document it was opened on, so "
            "this proves nothing")
        n_sources = len(dlg._sources)
        dlg._add_source(loose)
        qapp.processEvents()
        assert len(dlg._sources) == n_sources + 1, "the file did not load"
        assert dlg._page_doc_created == "", (
            "another measurement was added and the page still prints the "
            f"saved document's creation time {dlg._page_doc_created!r}")
    finally:
        dlg.close()


def test_a_leftover_member_is_restamped_with_a_type_its_kind_allows(
        tmp_path, qapp, monkeypatch):
    """Round 2B #8's third site, which its own test said out loud it did not
    guard: `_tid_for_block`, the type a member the Update DROPS is re-stamped
    with. A beta-34 Printing record of two verifications, one date unticked,
    Update: neither file may come out a Printing record, and the two files of
    the one document must agree.

    WHAT IT KILLS, MEASURED: neither D06 nor D07, and it is kept as a pin on
    the behaviour, not offered as their guard. D07
    (`_tid_for_block` unfitted) is an EQUIVALENT mutant on this path:
    dropping a member IS moving a control, and once a control has moved
    `_report_type_now()` answers from the sticky / run / default branches,
    every one of which is already fitted (measured on this fixture: "t2" at
    the press). So the "NOT GUARDED" note in test_round_2b_text_findings.py
    names a guard that cannot be written, not one that is missing. This test
    pins the behaviour itself, which is what a reader relies on.
    """
    import json
    from pathlib import Path
    from PyQt6.QtWidgets import QMessageBox
    from tests.test_a_generated_report_is_one_document import _messy_project
    from tests.test_generate_report_asks_what_to_do import (
        _a_real_document, _files, _pick_key, _press, _window)
    from workflow.measurement_report import (REPORT_TYPE_FULL,
                                             REPORT_TYPE_RECORD)
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
        doc_id = key.split(":", 1)[1]
        for f in _files(run):
            p = json.loads(f.read_text(encoding="utf-8"))
            doc = p.get("document") or {}
            if doc.get("id") == doc_id:
                doc["type"] = REPORT_TYPE_RECORD
                p["report_type"] = REPORT_TYPE_RECORD
                f.write_text(json.dumps(p), encoding="utf-8")
        # K19 (Knut, 2026-09-23): the list no longer offers a type the kind
        # refuses; the entry is let through to reach the fit it guards.
        dlg._entry_type = lambda e: REPORT_TYPE_FULL
        dlg._reload_sources()
        qapp.processEvents()
        dlg._saved_combo.setCurrentIndex(0)
        qapp.processEvents()
        _pick_key(dlg, key, qapp)
        assert dlg._report_type_now() == REPORT_TYPE_RECORD, \
            "the fixture did not reach a recorded Printing record"
        entry = next(d for d in dlg._saved_documents(dlg._run_ctx.run)
                     if d["key"] == key)
        assert len(entry["members"]) == 2, entry["members"]
        files = [Path(str(r.get("_origin_dir"))) / "reports" / n
                 for r, n in entry["members"]]
        dropped = dlg._run_key(dlg._history[0])
        dlg._hidden_runs.add(dropped)
        dlg._settings_touched()
        qapp.processEvents()
        del dlg._ask_update_or_create_new
        dlg._say_generated = lambda saved, failed: None
        monkeypatch.setattr(QMessageBox, "exec", _press("Update"))
        dlg._on_generate_report()
        qapp.processEvents()
        types = {str(f): (json.loads(f.read_text(encoding="utf-8"))
                          .get("document") or {}).get("type")
                 for f in files}
        assert len(types) == 2, types
        assert REPORT_TYPE_RECORD not in types.values(), (
            f"a verification's file was re-stamped a Printing record: {types}")
        assert len(set(types.values())) == 1, types
    finally:
        dlg.close()


def test_an_update_whose_archive_fails_writes_nothing(tmp_path, qapp,
                                                     monkeypatch):
    """Round A / 2A's ALL OR NOTHING, the half no test reached: every folder
    passes the write check, and then the ARCHIVE itself fails for one of them
    (`archive_report_files` returns it as unarchived: a full disk, a file
    locked by another program). The document must still be written whole or
    not at all.

    MUTANT D17: drop `_stuck |= set(_unarchived)`. The one folder whose
    archive failed is skipped and the other is rewritten, so one document
    says two things about itself.
    """
    from PyQt6.QtWidgets import QMessageBox
    import core.file_manager as FM
    from tests.test_a_generated_report_is_one_document import _messy_project
    from tests.test_generate_report_asks_what_to_do import (
        _a_real_document, _files, _pick_key, _press, _window)
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
        _pick_key(dlg, key, qapp)
        entry = next(d for d in dlg._saved_documents(dlg._run_ctx.run)
                     if d["key"] == key)
        from pathlib import Path
        dirs = sorted({(Path(str(r.get("_origin_dir"))) / "reports").resolve()
                       for r, _n in entry["members"]})
        assert len(dirs) == 2, dirs
        real = FM.archive_report_files

        def _one_folder_fails(paths, when=None, **kw):
            done, failed = real(
                [p for p in paths if Path(p).parent.resolve() != dirs[0]],
                when, **kw)
            return done, set(failed) | {dirs[0]}
        monkeypatch.setattr(FM, "archive_report_files", _one_folder_fails)
        before = {p: p.read_bytes() for p in _files(run)}
        dlg._detail_check.setChecked(False)
        qapp.processEvents()
        del dlg._ask_update_or_create_new
        said = {}
        dlg._say_generated = lambda saved, failed: said.update(
            saved=list(saved), failed=list(failed))
        monkeypatch.setattr(QMessageBox, "exec", _press("Update"))
        dlg._on_generate_report()
        qapp.processEvents()
        after = {p: p.read_bytes() for p in _files(run)}
        changed = [str(p) for p in after if before.get(p) != after[p]]
        assert not changed, (
            "an Update whose archive failed in one folder still rewrote: "
            f"{changed}")
        assert not said.get("saved"), said
    finally:
        dlg.close()


def test_a_rebuilt_older_report_keeps_its_document(tmp_path, qapp):
    """R2A-1 kept TWO keys across the rebuild of an older schema, and its own
    comment names both: the recorded type AND the document block ("its own
    creation stamp went too"). The R2A-1 test guards only the type.

    MUTANT D22: keep "report_type" and drop "document" from the kept keys.
    The rebuilt file loses its block, so the document's entry and its
    creation time are gone from the list.
    """
    import json
    from tests.test_a_generated_report_is_one_document import _messy_project
    from tests.test_generate_report_asks_what_to_do import (
        _a_real_document, _entries, _files, _pick_key, _window)
    from workflow.measurement_report import REPORT_SCHEMA, REPORT_TYPE_FULL
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=False, detail=False)
        _pick_key(dlg, key, qapp)
        created = str(dlg._doc_created or "")
        assert created
    finally:
        dlg.close()
    doc_id = key.split(":", 1)[1]
    stale = 0
    for f in _files(run):
        p = json.loads(f.read_text(encoding="utf-8"))
        if (p.get("document") or {}).get("id") == doc_id:
            p["schema"] = REPORT_SCHEMA - 1       # the window rebuilds it
            f.write_text(json.dumps(p), encoding="utf-8")
            stale += 1
    assert stale, "the document wrote no file"
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        assert key in [k for _l, k in _entries(dlg)], (
            f"the rebuilt report lost its document: {_entries(dlg)!r}")
        _pick_key(dlg, key, qapp)
        assert str(dlg._doc_created or "") == created
    finally:
        dlg.close()


def test_one_run_s_coverage_sentence_names_the_profile_run(tmp_path, qapp):
    """Round 2B #4/#10 reworded the one-run sentence to "this profile run";
    no test ever produced the one-run form (the K14 test's first state has no
    sentence at all), so any wording passed.

    MUTANT D29: "recorded for this run." again.
    """
    import re
    from tests.test_a_generated_report_is_one_document import _messy_project
    from tests.test_generate_report_asks_what_to_do import (
        _a_real_document, _pick_key, _window)
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, _run, vs = _messy_project(tmp_path, dates=2)
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=False, detail=False)
        _pick_key(dlg, key, qapp)
        body = re.sub(r"<[^>]+>", " ", dlg._report_body_html(
            dlg._runs_for_report(), for_pdf=False))
        body = re.sub(r"\s+", " ", body)
        assert ("This report covers 1 of the 2 measurements recorded for "
                "this profile run.") in body, body[-600:]
    finally:
        dlg.close()


def test_the_different_readings_note_has_its_bar_and_full_ink_text(
        qapp, monkeypatch):
    """R4 promised three things: a tinted box, "a full-ink bar down its left
    edge" and "full-ink text". The R4 test checks the tint only.

    MUTANTS D31 (drop the bar cell) and D32 (paint the text in the body's
    `text` colour instead of full ink).
    """
    import ui.dialogs.measurement_report_dialog as MRD
    # THE PRINTED PALETTE, pinned: in the dark window palette `text` and
    # `head` are the same grey, so D32 is invisible there, and the module
    # global `_C` is whatever the last page drawn left behind.
    monkeypatch.setattr(MRD, "_C", dict(MRD._LIGHT_REPORT))
    _C = MRD._C
    assert _C["text"] != _C["head"]
    dlg = MRD.MeasurementReportDialog.__new__(MRD.MeasurementReportDialog)
    out = dlg._scope_notes_html([{"kind": "patch_counts",
                                  "counts": [1617, 918]}])
    assert f"<td width='4' bgcolor='{_C['head']}'>" in out, out[:300]
    assert f"color:{_C['head']}'>" in out, out[:300]


def test_a_quick_check_page_puts_no_limit_in_brackets(tmp_path, qapp):
    """K3: *"no bracket and no note about 'the standard' for a set that is
    none"*. The K3 tests look for the NOTE only; the bracket around a
    recommended limit is the other half, and it is drawn from the recorded
    row's own `should`.

    MUTANT D37: strip the note in `_verdict_rows` and leave `should` True.
    """
    import re
    from tests.test_a_note_about_a_standard_needs_a_standard import (
        _run_with_a_should_copy)
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, v = _run_with_a_should_copy(tmp_path, "chromiq_quick")
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        dlg._detail_check.setChecked(True)
        qapp.processEvents()
        html_out = dlg._report_body_html(dlg._runs_for_report(),
                                         for_pdf=False)
        text = re.sub(r"<[^>]+>", " ", html_out)
        bracketed = re.findall(r"\(\d+\.\d+\)", text)
        assert not bracketed, (
            f"a Quick check page still brackets a limit: {bracketed[:5]}")
    finally:
        dlg.close()


def test_saving_the_pdf_logs_where_it_went_and_what_was_offered(
        tmp_path, qapp, monkeypatch, caplog):
    """K9: the export *"wrote nothing"* to the log, so Knut's report of the
    wrong folder could not be checked. Commit 1bd6ea22 says "the export says
    where it saved"; nothing tested that it does.

    MUTANT D43: delete the `log.info("measurement report PDF saved: ...")`.
    """
    import logging
    import ui.widgets
    from PyQt6.QtGui import QDesktopServices
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    out = tmp_path / "saved-here.pdf"
    offered = []

    def _save(*a, **k):
        offered.append((a, k))
        return str(out)
    monkeypatch.setattr(ui.widgets, "save_file_dialog", _save)
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda *a: True)
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    try:
        with caplog.at_level(logging.INFO):
            dlg._export_pdf()
        assert out.is_file()
        said = [r.getMessage() for r in caplog.records
                if "measurement report PDF saved" in r.getMessage()]
        assert said, "saving the PDF logged nothing"
        assert str(out) in said[-1], said[-1]
        assert "the dialog offered" in said[-1], said[-1]
    finally:
        dlg.close()


def test_clear_list_also_forgets_the_cleared_reports_settings(tmp_path, qapp):
    """R2A-6 reset four things on Clear list; its test checks the selected id
    only. The cleared report's own SETTINGS (`_loaded_doc`) are what
    `_document_settings` / `_document_limits` hand to "Judged against" and to
    Update, so a list cleared and refilled would go on being judged against a
    report that is no longer in it.

    MUTANT D20: drop `self._loaded_doc = None` from `_on_clear_list`.
    """
    from tests.test_a_generated_report_is_one_document import _messy_project
    from tests.test_generate_report_asks_what_to_do import (
        _a_real_document, _pick_key, _window)
    from workflow.measurement_report import REPORT_TYPE_FULL
    s, _fm, _run, vs = _messy_project(tmp_path, dates=2)
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
        dlg._saved_combo.setCurrentIndex(0)
        qapp.processEvents()
        _pick_key(dlg, key, qapp)
        assert dlg._document_settings() is not None, (
            "the picked report has no settings, so this proves nothing")
        dlg._on_clear_list()
        qapp.processEvents()
        assert dlg._document_settings() is None, (
            "the cleared report's settings still speak for the window")
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# K3's reader: an id this build does not know keeps what it was given
# ---------------------------------------------------------------------------
def test_a_set_id_this_build_does_not_know_keeps_its_recommendation():
    """`set_marks_recommendations`: *"every other set, and an id this build
    does not know, keeps what it was given"* (a report from a newer ChromIQ,
    CH-20). The K3 test covers a ChromIQ set, a standard's set and no id.

    MUTANT C02: `return d is not None and d.kind != "chromiq"`.
    """
    from workflow.compliance_sets import (limits_from_json,
                                          set_marks_recommendations)
    stored = {"grey_balance_neutral_ramp_avg": [3.0, "should"]}
    assert set_marks_recommendations("a_set_from_a_newer_chromiq")
    lim = limits_from_json(stored, "a_set_from_a_newer_chromiq")[
        "grey_balance_neutral_ramp_avg"]
    assert lim.is_should and lim.number == 3.0


# ---------------------------------------------------------------------------
# B8-740: Restore Used Chart takes EVERY chart field, and only those
# ---------------------------------------------------------------------------
def _restore_slot_with(tmp_path, live: dict, snap: dict) -> dict:
    import json
    from tests.test_a_restore_archives_the_side_file_it_overwrites import \
        _slot
    from workflow import verify_chart_snapshot as VS
    slot = _slot(tmp_path, live, snap)
    VS.restore_slot(slot)
    return json.loads((slot.live_dir / "meta.json").read_text(
        encoding="utf-8"))


def test_restore_takes_every_one_of_the_charts_fields(tmp_path):
    """Knut's ruling names the run's fields; `CHART_META_KEYS` names the
    chart's eleven, and the B8-740 test sets two of them. Each of the eleven
    is set differently live and in the snapshot here, and each must come back
    from the snapshot, spelled out rather than read off the tuple (a test
    that iterates the constant it guards cannot see a key leave it).

    MUTANTS V03 (drop "instrument", "paper"), V04 ("print_settings"), V08
    ("chart_notes"), V09 ("create_chart_ui").
    """
    chart_fields = ("instrument", "paper", "scanner_target_enabled",
                    "chart_notes", "verify_chart_notes",
                    "create_chart_settings", "create_chart_ui",
                    "print_settings", "editor_layout", "editor_basename",
                    "editor_recipe")
    live = {k: f"live {k}" for k in chart_fields}
    live["description"] = "the run's"
    snap = {k: f"snapshot {k}" for k in chart_fields}
    got = _restore_slot_with(tmp_path, live, snap)
    wrong = {k: got.get(k) for k in chart_fields if got.get(k) != snap[k]}
    assert not wrong, f"chart fields not restored from the snapshot: {wrong}"
    assert got["description"] == "the run's"


def test_a_chart_field_the_snapshot_never_had_is_not_kept_from_live(
        tmp_path):
    """A chart field that is live but absent from the snapshot belongs to the
    chart that is being REPLACED, so it goes: keeping it would pin the new
    chart's notes (or recipe) onto the chart the user restored.

    MUTANT V06: drop the `out.pop(key, None)` branch of `merge_restored_meta`.
    """
    got = _restore_slot_with(
        tmp_path,
        {"description": "keep", "chart_notes": "about the chart being replaced",
         "create_chart_settings": {"targen_-f": 400}},
        {"create_chart_settings": {"targen_-f": 210}})
    assert "chart_notes" not in got, got
    assert got["create_chart_settings"] == {"targen_-f": 210}
    assert got["description"] == "keep"


# ---------------------------------------------------------------------------
# K1 and B8-800 on the Create Chart tab
# ---------------------------------------------------------------------------
def test_the_importer_checks_the_maximised_family_against_its_own_base():
    """`import_knut_presets._shipped_base` is what makes a drifting batch fail
    to validate; the existing guard lists cm/p3/i1/i175 only, so the K1 entry
    for i175max could vanish and the importer would check that family against
    nothing (an empty base: *"a brand-new one has nothing to disagree
    with"*).

    MUTANT T09: delete `"i175max": "_I1_75_MAX_BASE"` from the map.
    """
    import importlib.util
    from pathlib import Path
    from ui.tabs.tab_chart import _I1_75_MAX_BASE
    spec = importlib.util.spec_from_file_location(
        "_imp_r3c", Path(__file__).resolve().parent.parent / "scripts"
        / "import_knut_presets.py")
    mod = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = mod          # its dataclasses look themselves up
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(spec.name, None)
    assert mod._shipped_base(mod.FAMILIES["i175max"]) == _I1_75_MAX_BASE


def _verification_tab(qapp, tmp_path):
    from tests.test_the_preset_button_is_small_fast_and_where_it_belongs \
        import _env, _tab
    from core.measurement_target import RUN_TYPE_VERIFICATION
    settings, fm, ctl = _env(tmp_path)
    tab = _tab(settings, fm, ctl)
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab.show()
    qapp.processEvents()
    tab._manual_btn.click()
    qapp.processEvents()
    tab._sync_preset_verify_visibility()
    qapp.processEvents()
    return tab, ctl


def test_the_buttons_row_is_hidden_with_the_button(qapp, tmp_path):
    """The row container is in `_sync_preset_verify_visibility`'s list since
    B8-800; with it left out, a profiling run keeps an empty row in the
    Presets group, whose layout still reserves it.

    MUTANT T04: drop "_preset_verify_row" from that list.
    """
    from core.measurement_target import RUN_TYPE_PROFILING
    tab, ctl = _verification_tab(qapp, tmp_path)
    try:
        assert tab._preset_verify_row.isVisibleTo(tab)
        ctl.set_run_type(RUN_TYPE_PROFILING)
        tab._sync_preset_verify_visibility()
        qapp.processEvents()
        assert not tab._preset_verify_btn.isVisibleTo(tab)
        assert tab._preset_verify_row.isHidden(), (
            "the button is hidden and its row is still shown")
    finally:
        tab.close()
        tab.deleteLater()
        qapp.processEvents()
