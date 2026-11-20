"""X-Rite i1Pro 3 and i1Pro 2: keep M0, M1 and M2 from every scan (Preferences > Beta):
the findings of the independent review of 2026-11-15, each pinned.

* F1: a main file that records no condition is not offered as "M0, as
  measured" when its pair shows otherwise. Its condition is the one its two
  condition files leave free; when they do not show it (one file, or all
  three), it is offered only as it is and the other conditions are greyed
  with the reason. No pair at all: M0, as in 4.3.40.
* F2: covered in tests/test_i1pro3_conditions_verification.py (the profile's
  RECORDED condition is followed with the Beta off too, a read only).
* F4: the engine renames the main file into place BEFORE it removes the pair
  it wrote earlier in the session, and writes the new pair before both.
* F5: a typed value (external values, -x) never keeps a pair, and that path
  cannot run with the conditions on today.
* F6: a preset saved again under its own name with the Beta off keeps its
  stored "Build from".
* F7: another instrument than an i1Pro 3: no Measure log line, no empty
  conditions/ folder left.
* Pruning deletes only files whose own header says ChromIQ wrote them.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

from core.file_manager import Run
from workflow import i1pro3_conditions as C

from tests.test_i1pro3_conditions_verification import _pair, _ti3

ROOT = Path(__file__).resolve().parents[1]
HELPER_C = ROOT / "native" / "chartread_helper" / "chromiq_chartread.c"


def _bare_sibling(main: Path, cond: str, w: str) -> Path:
    """A file under the pair's name WITHOUT the engine's header lines (the
    reviewer's case_unrecorded has its M0 file like this)."""
    dst = Run.for_dir(main.parent).condition_ti3(cond, measurement=main)
    return _ti3(dst, w=w, head="")


# ---------------------------------------------------------------------------
# F1
# ---------------------------------------------------------------------------

def test_f1_the_reviewers_case_is_not_offered_as_m0(tmp_path):
    """case_unrecorded: a session measured with -F u (M2) ended abnormally,
    so the main records nothing and holds M2 readings; beside it the M0 and
    M1 files. The main is M2, never "M0, as measured"."""
    main = _ti3(tmp_path / "P" / "runs" / "run1" / "Rev.ti3", w="85", head="")
    _bare_sibling(main, "M0", "86")
    m1 = _pair(main, "M1", "90")
    assert C.file_condition(main) == "M2"
    ch = C.choices_for(main)
    assert [(c.cond, c.main) for c in ch] == [
        ("M2", True), ("M0", False), ("M1", False)]
    assert ch[0].path == main
    # the M0 file there does not say it belongs to these readings: greyed
    assert not ch[1].usable and "does not say that it holds" in ch[1].reason
    assert ch[2].usable and ch[2].path == m1
    assert C.condition_file(main, "M0") is None


def test_f1_the_engines_own_pair_makes_m0_usable(tmp_path):
    main = _ti3(tmp_path / "P" / "runs" / "run1" / "Rev.ti3", w="85", head="")
    m0 = _pair(main, "M0", "86")
    _pair(main, "M1", "90")
    ch = C.choices_for(main)
    assert ch[0].cond == "M2" and ch[0].main
    assert ch[1].cond == "M0" and ch[1].usable and ch[1].path == m0


def test_f1_when_the_pair_does_not_show_it_nothing_is_offered(tmp_path):
    main = _ti3(tmp_path / "P" / "runs" / "run1" / "Rev.ti3", w="85", head="")
    _pair(main, "M1", "90")           # one file: M0 or M2, nobody can tell
    assert C.file_condition(main) == ""
    ch = C.choices_for(main)
    assert ch[0].main and ch[0].cond == "" and ch[0].path == main
    assert [c.cond for c in ch[1:]] == ["M0", "M1", "M2"]
    assert all(not c.usable and "does not record" in c.reason
               for c in ch[1:])
    assert C.condition_file(main, "M1") is None
    assert C.condition_file(main, "M0") is None
    for c in C.CONDITIONS:            # all three: just as unclear
        _pair(main, c, "91")
    assert C.file_condition(main) == ""


def test_f1_no_pair_and_no_record_is_m0_as_in_4340(tmp_path):
    main = _ti3(tmp_path / "P" / "runs" / "run1" / "Rev.ti3", w="85", head="")
    assert C.file_condition(main) == "M0"
    assert C.choices_for(main)[0].cond == "M0"


def test_f1_a_recorded_condition_always_wins(tmp_path):
    main = _ti3(tmp_path / "P" / "runs" / "run1" / "Rev.ti3", w="85", head=(
        'KEYWORD "MEASUREMENT_CONDITION"\nMEASUREMENT_CONDITION "M1"'))
    _pair(main, "M0", "86")
    _pair(main, "M2", "80")
    assert C.file_condition(main) == "M1"


def test_f1_the_build_profile_list_names_no_condition_for_it():
    src = (ROOT / "ui" / "tabs" / "tab_profile.py").read_text(encoding="utf-8")
    assert 'tr("As measured (condition not recorded)")' in src


# ---------------------------------------------------------------------------
# F4 / F5 (the engine's source; the real helper's behaviour is in
# tests/test_i1pro3_conditions_engine.py: only the newest pair stays)
# ---------------------------------------------------------------------------

def _body(src: str, head: str) -> str:
    i = src.index(head)
    j = src.index("\n}\n", i)
    return src[i:j]


def test_f4_the_old_pair_goes_only_after_the_main_is_in_place():
    src = HELPER_C.read_text(encoding="utf-8", errors="replace")
    autosave = _body(src, "static void cq_write_ti3_atomic(void) {")
    w = autosave.index("cq_cond_write(tmpname);")
    r = autosave.index("rename(tmpname, realname)")
    c = autosave.index("cq_cond_commit();")
    assert w < r < c
    # a failed rename returns before the commit: the old pair stays
    fail = autosave.index('"autosave_rename\\"', r)
    assert autosave.index("return;", fail) < c
    write = _body(src, "static void cq_cond_write(const char *mainfile) {")
    assert "remove(path)" not in write and "cq_cond_last" not in write
    assert "cq_rename_over(tmp, path)" in write   # the pair under temp names
    commit = _body(src, "static void cq_cond_commit(void) {")
    assert "remove(path)" in commit and "cq_cond_last" in commit
    final = src[src.index("/* And save the result */"):]
    assert final.index("cq_cond_write(outname);") < final.index(
        "cq_cond_commit();") < final.index('cq_emit_simple("done");')


def test_f4_the_helper_build_string_is_the_new_one():
    h = (ROOT / "native" / "chartread_helper" / "chromiq_ext.h").read_text(
        encoding="utf-8")
    # 2026-11-17a (the i1iO 2 table scan), 17b (its button wait), 18a (the
    # i1Pro 2 dual-scan conditions), 18b (its resume rule) and 18c (its
    # device side), 18d (its safety fixes) and 18e (the dual scan on the i1iO 2
    # table), 19a (its fix round), 19b (a calibration clears the armed pass), 19c (the hand dual
    # scan's gaps, 4.3.49) and 19d (the record kept after an end) keep every
    # token of 16d
    assert re.search(r"chromiq-chartread 2026-11-(16d|17a|17b|18a|18b|18c|18d|18e|19a|19b|19c|19d|20a|20b|20c) ", h)
    assert "+conditions-commit-last" in h


def test_f5_a_typed_value_never_keeps_a_pair():
    src = HELPER_C.read_text(encoding="utf-8", errors="replace")
    i = src.index("/* Read the external sample */")
    typed = src[i:src.index("/* We've read the spot sample */", i)]
    assert 'cq_cond_lose("typed");' in typed
    assert typed.index("cq_cond_lose(") < typed.index("cq_write_ti3_atomic();")
    # ... and today it cannot run with the conditions on at all: they are
    # only ever set up for a session that reads an instrument
    assert re.search(r"if \(xtern == 0\)\s*\n\s*cq_cond_for_session\(", src)
    assert src.count("cq_cond_for_session(it,") == 1


# ---------------------------------------------------------------------------
# F6
# ---------------------------------------------------------------------------

def test_f6_saving_a_preset_again_with_the_beta_off_keeps_build_from(
        monkeypatch):
    from ui.tabs import tab_profile as TP

    class _Dlg:
        def __init__(self, *_a):
            pass

        def __getattr__(self, _n):
            return lambda *a, **k: None

        def exec(self):
            return True

        def textValue(self):
            return " Mine "

    monkeypatch.setattr(TP, "QInputDialog", _Dlg)
    stored = {"Mine": {"colprof_quality": "h", C.BUILD_FROM_KEY: "M1"},
              "Other": {C.BUILD_FROM_KEY: "M2"}}
    saved = {}
    fake = SimpleNamespace(
        _m_collect_preset_data=lambda: {"colprof_quality": "u"},
        _m_load_presets=lambda: {k: dict(v) for k, v in stored.items()},
        _m_save_presets=lambda p: saved.update(p),
        _m_populate_preset_combo=lambda *a, **k: None)
    TP.TabProfile._on_m_preset_save(fake)
    assert saved["Mine"] == {"colprof_quality": "u", C.BUILD_FROM_KEY: "M1"}
    assert saved["Other"] == {C.BUILD_FROM_KEY: "M2"}
    # with the Beta on the preset carries the choice made now
    fake._m_collect_preset_data = lambda: {"colprof_quality": "u",
                                           C.BUILD_FROM_KEY: ""}
    TP.TabProfile._on_m_preset_save(fake)
    assert saved["Mine"][C.BUILD_FROM_KEY] == ""


# ---------------------------------------------------------------------------
# F7
# ---------------------------------------------------------------------------

def test_f7_another_instrument_says_nothing_and_leaves_no_folder(tmp_path):
    from workflow.measure_manager import MeasureManager
    from tests.test_i1pro2_lights_beta_option import _Runner
    m = MeasureManager(_Runner())
    made = tmp_path / "run1" / "conditions"
    made.mkdir(parents=True)
    m._conditions_made_dir = made
    lines = []
    m._on_conditions_event({"event": "conditions", "active": False,
                            "why": "instrument"}, lines.append)
    assert lines == [] and not made.exists()
    # a folder that was there before (it holds the run's pairs) stays
    made.mkdir()
    m._conditions_made_dir = None
    m._on_conditions_event({"event": "conditions", "active": False,
                            "why": "instrument"}, lines.append)
    assert lines == [] and made.is_dir()


def test_f7_the_session_end_takes_an_empty_folder_away(tmp_path):
    run = Run.for_dir(tmp_path / "P" / "runs" / "run1")
    run.condition_dir.mkdir(parents=True)
    run.verification_condition_dir.mkdir(parents=True)
    C.prune_run(run)
    assert not run.condition_dir.exists()
    assert not run.verification_condition_dir.exists()
    main = _ti3(run.dir / "P.ti3")
    kept = _pair(main, "M1", "90")
    C.prune_run(run)
    assert kept.is_file()


# ---------------------------------------------------------------------------
# pruning: only what it can prove it wrote
# ---------------------------------------------------------------------------

def test_pruning_never_deletes_a_file_only_named_like_ours(tmp_path):
    import os
    import time
    run = Run.for_dir(tmp_path / "P" / "runs" / "run1")
    gone_main = _ti3(tmp_path / "elsewhere" / "x.ti3", w="70")
    ours = _pair(gone_main, "M1", "75")
    run.condition_dir.mkdir(parents=True)
    ours = ours.replace(run.condition_dir / ours.name)
    h = C.data_block_hash(gone_main)
    stranger = _ti3(run.condition_dir / f"{h}-M2.ti3", w="60", head="")
    other_key = _ti3(run.condition_dir / "5-0000abcd-M1.ti3", w="61", head=(
        'KEYWORD "MEASUREMENT_CONDITION"\nMEASUREMENT_CONDITION "M1"\n'
        'KEYWORD "CHROMIQ_CONDITION_OF"\nCHROMIQ_CONDITION_OF "6-0000abcd"'))
    t = time.time() - 3600
    for p in (ours, stranger, other_key):
        os.utime(p, (t, t))
    assert C.prune_run(run) == [ours]
    assert stranger.is_file() and other_key.is_file()


def test_a_temporary_file_a_crash_left_is_pruned_only_when_it_is_ours(tmp_path):
    """4.3.42: the engine writes each condition file as <hash>-Mx.ti3.cqtmp
    and renames it into place; a crash in between left the temporary file
    for ever. Pruning removes it: only that name, only in conditions/, only
    when older than 10 minutes. Anything else stays."""
    import os
    import time
    run = Run.for_dir(tmp_path / "P" / "runs" / "run1")
    run.condition_dir.mkdir(parents=True)
    old = time.time() - 3600

    def made(path, age=old):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("CTI3\n", encoding="latin-1")
        os.utime(path, (age, age))
        return path
    stray = made(run.condition_dir / "12-0123abcd-M2.ti3.cqtmp")
    fresh = made(run.condition_dir / "12-0123abcd-M1.ti3.cqtmp", time.time())
    other_name = made(run.condition_dir / "notes.ti3.cqtmp")
    main_tmp = made(run.dir / "P.ti3.cqtmp")          # M3: the kept save
    elsewhere = made(tmp_path / "P" / "12-0123abcd-M2.ti3.cqtmp")
    gone = C.prune_run(run)
    assert gone == [stray] and not stray.exists()
    for p in (fresh, other_name, main_tmp, elsewhere):
        assert p.is_file(), p


def test_the_help_names_the_condition_not_recorded_case_and_the_comparison():
    """4.3.42: "Why an entry can be greyed out" names the measurement that
    records no condition (review F1's case), and the honest limit says what
    was compared: M0, M1 and M2 with i1Profiler on one i1Pro 3 and one
    paper, 0.15 to 0.19 dE00 apart on average (the owner's figures,
    2026-11-16), and that it was one instrument and one paper. The earlier
    M1-only figures (0.2 to 0.3) and "M0 and M2 not yet" are gone."""
    from ui.dialogs.settings_dialog import (i1pro3_conditions_confirmation,
                                            i1pro3_conditions_help)
    from ui.tabs.tab_profile import build_from_help
    b = " ".join(build_from_help().split())
    assert "As measured (condition not recorded)" in b
    c = " ".join(i1pro3_conditions_confirmation().split())
    for text in (b, " ".join(i1pro3_conditions_help().split()), c):
        assert "M0, M1 and M2 values" in text
        assert "0.15 to 0.19 ΔE00 on average" in text
        # review 2: bracketed, so "one paper" is asserted for every text
        assert "one paper" in text and (
            "not yet" in text or "have not been compared yet" in text)
        for gone in ("0.2 to 0.3", "0.12", "M0 and M2 values have not",
                     "M0 and M2 values not yet"):
            assert gone not in text, gone
