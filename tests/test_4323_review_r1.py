"""4.3.23 review round 1: the findings, each pinned.

S1  the CHANGELOG said -F is not passed when the option is switched ON.
S2  a 4.3.22-or-older import ("i1Pro 3", no spectra) was told to measure
    with an i1Pro, which it was; it is told to import the .mxf again.
S3  the Measure tab records the condition it measured under (-F), merges
    of an M1/M2 measurement with one of another or no condition are
    refused, and the FWA gate refuses -f for such chartread files too.
S4  an i1Profiler CGATS .txt import records the condition its
    MEASUREMENT_SOURCE names (Filter=no / D50 / UVcut / Polarized), and
    one that names none gets no -f.
M1  the Measurement Report keeps one .mxf under two conditions apart.
M3  "instrument differs" compares instrument families.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# S1
# ---------------------------------------------------------------------------

def _unreleased() -> str:
    # The 4.3.23 notes, under their version heading since the release (an
    # "## Unreleased" above them is the next release's, 4.3.24 on).
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    return text.split("## v4.3.23", 1)[1].split("\n## v", 1)[0]


def test_s1_the_changelog_says_minus_f_is_left_out_while_the_option_is_off():
    text = _unreleased()
    assert "and then ChromIQ does not pass -F at all" not in text
    assert ("While it is off (the default), ChromIQ does not pass -F at all"
            in text)


# ---------------------------------------------------------------------------
# S2
# ---------------------------------------------------------------------------

def test_s2_an_old_import_without_spectra_is_told_to_import_again():
    from workflow.fwa_gate import fwa_refusal
    r = fwa_refusal("i1Pro 3", has_spectral=False)
    assert r is not None and r.kind == "reimport"
    text = r.reason
    assert "import the i1Profiler file (.mxf or .cxf) again" in text
    assert "spectral readings" in text
    assert "measurement condition" in text
    assert "such as an i1Pro" not in text      # the no-spectra advice


def test_s2_a_file_without_spectra_and_an_argyll_name_stays_no_spectra():
    from workflow.fwa_gate import fwa_refusal
    assert fwa_refusal("X-Rite i1 Pro 3", has_spectral=False).kind == \
        "no_spectra"
    assert fwa_refusal(None, has_spectral=False).kind == "no_spectra"
    # A CR30 file names an instrument ArgyllCMS has no lamp for, and no
    # spectra: the spectra are what it lacks first.
    assert fwa_refusal("CR30", has_spectral=False).kind == "no_spectra"


def test_s2_an_old_import_with_spectra_is_still_reimport():
    from workflow.fwa_gate import fwa_refusal
    assert fwa_refusal("i1Pro 3", has_spectral=True).kind == "reimport"


# ---------------------------------------------------------------------------
# S3 (Basti's ruling, 2026-11-03)
# ---------------------------------------------------------------------------

_FMT = "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z"


def _ti3(path: Path, condition=None, instrument="X-Rite i1 Pro 3",
         spectral=True, crlf=False) -> Path:
    head = ["CTI3", "", 'DESCRIPTOR "Argyll Calibration Target chart '
            'information 3"', 'ORIGINATOR "Argyll chartread"',
            f'TARGET_INSTRUMENT "{instrument}"']
    if condition:
        head += ['KEYWORD "MEASUREMENT_CONDITION"',
                 f'MEASUREMENT_CONDITION "{condition}"']
    fmt = _FMT
    rows = ['1 "A1" 10 20 30 11.0 12.0 13.0', '2 "A2" 40 50 60 21.0 22.0 23.0']
    if spectral:
        head += ['SPECTRAL_BANDS "2"', 'SPECTRAL_START_NM "380.000000"',
                 'SPECTRAL_END_NM "390.000000"']
        fmt += " SPEC_380 SPEC_390"
        rows = [r + " 50.0 51.0" for r in rows]
    head += ['COLOR_REP "iRGB_XYZ"', "", f"NUMBER_OF_FIELDS {len(fmt.split())}",
             "BEGIN_DATA_FORMAT", fmt, "END_DATA_FORMAT", "",
             f"NUMBER_OF_SETS {len(rows)}", "BEGIN_DATA", *rows, "END_DATA", ""]
    nl = "\r\n" if crlf else "\n"
    path.write_bytes(nl.join(head).encode("ascii"))
    return path


def test_s3_the_filter_names_the_condition():
    from workflow.measurement_condition import (condition_for_filter,
                                                filter_code_from_args)
    assert condition_for_filter("n") == "M0"
    assert condition_for_filter("5") == "M1"
    assert condition_for_filter("u") == "M2"
    assert condition_for_filter("p") == "M3"
    assert condition_for_filter("6") is None      # D65: no ISO condition
    assert condition_for_filter(None) is None
    assert filter_code_from_args("-F 5 -H") == "5"
    assert filter_code_from_args("-H -Fu") == "u"
    assert filter_code_from_args("-H") is None
    assert filter_code_from_args("") is None


def test_s3_recording_the_condition_changes_only_the_header(tmp_path):
    from workflow.measurement_condition import read_condition, record_condition
    for crlf in (False, True):
        p = _ti3(tmp_path / f"cr{crlf}.ti3", crlf=crlf)
        before = p.read_bytes()
        assert read_condition(p) is None
        assert record_condition(p, "M1")
        after = p.read_bytes()
        assert read_condition(p) == "M1"
        data = lambda b: b.split(b"BEGIN_DATA_FORMAT", 1)[1]  # noqa: E731
        assert data(before) == data(after)
        nl = b"\r\n" if crlf else b"\n"
        assert b'KEYWORD "MEASUREMENT_CONDITION"' + nl in after
        assert after.startswith(b"CTI3")
        # Once only; a second record of the same is no change.
        assert not record_condition(p, "M1")
        assert after.count(b"MEASUREMENT_CONDITION") == 2
        # A different one replaces the value, never adds a second.
        assert record_condition(p, "M2")
        assert read_condition(p) == "M2"
        assert p.read_bytes().count(b"MEASUREMENT_CONDITION") == 2


def test_s3_the_measure_tab_records_the_condition_of_its_reads():
    """Taken from -F at Start, written when the session ends, BEFORE the
    yellow memory's checksum is taken."""
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    start = inspect.getsource(TabMeasure._on_start)
    assert "self._session_filter = filter_code_from_args(" in start
    assert start.index("self._session_filter =") < \
        start.index("self._ti3_mtime_before = (")
    done = inspect.getsource(TabMeasure._on_measure_done)
    assert done.index("self._record_measurement_condition_at_end()") < \
        done.index("self._save_confirmed_memory_at_end()")
    assert done.index("self._finish_session_guard()") < \
        done.index("self._record_measurement_condition_at_end()")


class _TabStandIn:
    pass


def _record_at_end(tmp_path, code, *, fresh=True, condition=None):
    import os
    from ui.tabs.tab_measure import TabMeasure
    ti1 = tmp_path / "chart.ti1"
    ti1.write_text("CTI1\n", encoding="utf-8")
    ti3 = _ti3(tmp_path / "chart.ti3", condition=condition)
    t = _TabStandIn()
    t._session_filter = code
    t._ti1_path = ti1
    mtime = ti3.stat().st_mtime
    t._ti3_mtime_before = (mtime - 10) if fresh else mtime
    if not fresh:
        os.utime(ti3, (mtime, mtime))
    TabMeasure._record_measurement_condition_at_end(t)
    assert t._session_filter is None
    from workflow.measurement_condition import read_condition
    return read_condition(ti3)


def test_s3_each_filter_is_recorded_in_the_file_the_session_wrote(tmp_path):
    for code, want in (("n", "M0"), ("5", "M1"), ("u", "M2"), ("p", "M3")):
        sub = tmp_path / code
        sub.mkdir()
        assert _record_at_end(sub, code) == want


def test_s3_no_filter_records_nothing(tmp_path):
    """Unknown, judged as before (the default: no -F is passed)."""
    assert _record_at_end(tmp_path, None) is None
    (tmp_path / "d65").mkdir()
    assert _record_at_end(tmp_path / "d65", "6") is None


def test_s3_a_measurement_put_back_is_not_stamped(tmp_path):
    """The session guard restores the previous file with its own time; that
    file was not measured under this session's -F."""
    assert _record_at_end(tmp_path, "5", fresh=False) is None


def _merge_pair(tmp_path, fresh_cond, pre_cond):
    from workflow.ti3_merge import merge_refusal
    a = _ti3(tmp_path / f"fresh_{fresh_cond}_{pre_cond}.ti3", fresh_cond)
    b = _ti3(tmp_path / f"pre_{fresh_cond}_{pre_cond}.ti3", pre_cond)
    return merge_refusal(a, b)


def test_s3_two_different_recorded_conditions_are_refused(tmp_path):
    """Round 2 (S-A3) narrowed round 1's rule: only two RECORDED, different
    conditions are refused; "not recorded" against M1/M2/M3 is asked
    (tests/test_4323_review_r2a.py)."""
    for fresh, pre in (("M1", "M2"), ("M0", "M1"), ("M2", "M0"),
                       ("M3", "M1")):
        refusal = _merge_pair(tmp_path, fresh, pre)
        assert refusal, (fresh, pre)
        for c in (fresh, pre):
            assert c in refusal, (fresh, pre, refusal)
        assert "not recorded" not in refusal
        assert "measure" in refusal and ".mxf" in refusal
        assert "—" not in refusal
    for fresh, pre in (("M1", None), (None, "M1"), ("M2", None),
                       (None, "M2"), ("M3", None)):
        assert _merge_pair(tmp_path, fresh, pre) is None, (fresh, pre)


def test_s3_unknown_with_m0_or_unknown_merges_as_before(tmp_path):
    for fresh, pre in ((None, None), ("M0", None), (None, "M0"),
                       ("M0", "M0"), ("M1", "M1"), ("M2", "M2")):
        assert _merge_pair(tmp_path, fresh, pre) is None, (fresh, pre)


def test_s3_the_tools_merge_refuses_two_recorded_conditions(tmp_path):
    import pytest
    from workflow.ti3_merge import Ti3MergeError, merge_measurements
    a = _ti3(tmp_path / "a.ti3", "M1")
    b = _ti3(tmp_path / "b.ti3", "M2")
    with pytest.raises(Ti3MergeError) as exc:
        merge_measurements([a, b], tmp_path / "out.ti3", bin_dir=None)
    assert "b.ti3" in exc.value.message and "M1" in exc.value.message
    assert not (tmp_path / "out.ti3").exists()


def test_s3_the_gate_refuses_fwa_for_a_chartread_m1_or_m2(tmp_path):
    from workflow.fwa_gate import fwa_refusal_for_file
    from workflow.measurement_condition import record_condition
    for cond in ("M1", "M2", "M3"):
        p = _ti3(tmp_path / f"{cond}.ti3", instrument="X-Rite i1 Pro 3")
        assert fwa_refusal_for_file(p) is None         # no -F: as before
        record_condition(p, cond)
        r = fwa_refusal_for_file(p)
        assert r is not None and r.kind == "condition" and r.condition == cond
    p = _ti3(tmp_path / "M0.ti3", instrument="X-Rite i1 Pro 3")
    record_condition(p, "M0")
    assert fwa_refusal_for_file(p) is None


# ---------------------------------------------------------------------------
# S4: the i1Profiler CGATS .txt route
# ---------------------------------------------------------------------------

def _i1p_txt(path: Path, source: "str | None", instrument="i1Pro 3") -> Path:
    """An i1Profiler CGATS export header as i1Profiler writes it: tabs, the
    condition in MEASUREMENT_SOURCE ("Filter=no | D50 | UVcut | Polarized",
    i1Profiler's own strings), or "Not specified"."""
    lines = ["CGATS.17", 'ORIGINATOR\t"i1Profiler"',
             'CREATED\t"October 27, 2026"', f'INSTRUMENTATION\t"{instrument}"']
    if source is not None:
        lines.append(f'MEASUREMENT_SOURCE\t"{source}"')
    lines += ['KEYWORD\t"SampleID"', "NUMBER_OF_FIELDS\t4",
              "BEGIN_DATA_FORMAT", "SampleID\tRGB_R\tRGB_G\tRGB_B",
              "END_DATA_FORMAT", "NUMBER_OF_SETS\t1", "BEGIN_DATA",
              "1\t10\t20\t30", "END_DATA", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_s4_the_condition_is_read_from_measurement_source(tmp_path):
    from workflow.reference_convert import read_txt_condition
    want = {"Filter=No": "M0", "Filter=no": "M0", "Filter=D50": "M1",
            "Filter=UVcut": "M2", "Filter=Polarized": "M3"}
    for flt, cond in want.items():
        src = f"Illumination=D50\tObserverAngle=2\tWhiteBase=Abs\t{flt}"
        assert read_txt_condition(_i1p_txt(tmp_path / "a.txt", src)) == cond
    for unknown in ("Not specified", "Illumination=D50 ObserverAngle=2",
                    "Filter=Something", None):
        assert read_txt_condition(_i1p_txt(tmp_path / "b.txt", unknown)) \
            is None, unknown


def test_s4_the_txt_import_records_the_condition(tmp_path):
    from workflow.measurement_condition import read_condition
    from workflow.reference_convert import finalize_converted_ti3
    for flt, cond in (("Filter=UVcut", "M2"), ("Not specified", None)):
        ti3 = _ti3(tmp_path / f"{cond}.ti3",
                   instrument="GretagMacbeth Spectrolino")   # txt2ti3's
        src = _i1p_txt(tmp_path / f"{cond}.txt",
                       f"Illumination=D50\tObserverAngle=2\t{flt}"
                       if cond else flt)
        instr, _date = finalize_converted_ti3(ti3, src, None)
        assert instr == "X-Rite i1 Pro 3"
        assert read_condition(ti3) == cond


def test_s4_fwa_is_refused_for_an_i1profiler_import_of_unknown_condition(
        tmp_path):
    from workflow.fwa_gate import fwa_refusal_for_file
    from workflow.reference_convert import finalize_converted_ti3
    ti3 = _ti3(tmp_path / "u.ti3", instrument="GretagMacbeth Spectrolino")
    finalize_converted_ti3(ti3, _i1p_txt(tmp_path / "u.txt", "Not specified"),
                           None)
    r = fwa_refusal_for_file(ti3)
    assert r is not None and r.kind == "import_condition"
    assert "does not say which measurement condition" in r.reason
    assert "M0" in r.reason and ".mxf" in r.reason
    assert "—" not in r.reason
    assert r.log_line.startswith("[NOTE]")
    # The same import that names M0 gets -f; M1 is refused as M1.
    ok = _ti3(tmp_path / "m0.ti3", instrument="GretagMacbeth Spectrolino")
    finalize_converted_ti3(ok, _i1p_txt(tmp_path / "m0.txt", "Filter=no"),
                           None)
    assert fwa_refusal_for_file(ok) is None
    m1 = _ti3(tmp_path / "m1.ti3", instrument="GretagMacbeth Spectrolino")
    finalize_converted_ti3(m1, _i1p_txt(tmp_path / "m1.txt", "Filter=D50"),
                           None)
    assert fwa_refusal_for_file(m1).kind == "condition"


def test_s4_a_chartread_file_without_a_condition_is_judged_as_before(
        tmp_path):
    from workflow.fwa_gate import fwa_refusal_for_file
    assert fwa_refusal_for_file(_ti3(tmp_path / "c.ti3",
                                     instrument="X-Rite i1 Pro 3")) is None


# ---------------------------------------------------------------------------
# M1: one .mxf, two conditions, two sources
# ---------------------------------------------------------------------------

def _report_host():
    import types
    from ui.dialogs.measurement_report_dialog import (
        MeasurementReportDialog as M)
    host = types.SimpleNamespace(_sources=[], _ti3=None)
    for n in ("_source_key", "_source_keys", "_source_has_moved_on",
              "_reread_one_source", "_source_signature"):
        setattr(host, n, types.MethodType(getattr(M, n), host))
    host._disk_stamp = M._disk_stamp
    host._reload_sources = lambda: None
    host._rebuild_from_sources = lambda: None
    host._gather_runs = lambda t: (t.stem, [{"created": "2026-01-01",
                                             "ti3": str(t)}])
    return host, types.MethodType(M._append_source, host)


def test_m1_the_same_mxf_under_two_conditions_is_two_sources(
        qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "workflow.measurement_report.list_project_reports", lambda d: [])
    origin = tmp_path / "sheet.mxf"
    origin.write_text("<cxf/>", encoding="utf-8")
    host, append = _report_host()
    conv = {}
    for i, cond in enumerate(("M1", "M2", "M1")):
        d = tmp_path / f"tmp{i}"
        d.mkdir()
        conv[i] = _ti3(d / "sheet.ti3", cond)
    assert append(conv[0], origin=origin) is True
    assert append(conv[1], origin=origin) is True    # was dropped in silence
    assert append(conv[2], origin=origin) is False   # M1 again: a duplicate
    assert [s["condition"] for s in host._sources] == ["M1", "M2"]
    sig = host._source_signature()
    assert len(set(sig)) == 2


def test_m1_the_list_header_names_the_condition():
    import inspect
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    src = inspect.getsource(MeasurementReportDialog._rebuild_from_sources)
    assert 'condition_name(_cond)' in src


# ---------------------------------------------------------------------------
# M3: the i1Pro family is one instrument in "instrument differs"
# ---------------------------------------------------------------------------

def _scope_warnings(*instruments):
    from workflow.measurement_report import report_scope
    runs = [{"chart": "P", "instrument": inst,
             "created": f"2026-11-0{i + 1}T10:00:00"}
            for i, inst in enumerate(instruments)]
    return [w for w in report_scope(runs)["warnings"]
            if w["kind"] == "instrument"]


def test_m3_a_chartread_i1pro_and_an_i1pro3_import_are_one_instrument():
    assert _scope_warnings("GretagMacbeth i1 Pro", "X-Rite i1 Pro 3") == []
    assert _scope_warnings("GretagMacbeth i1 Pro", "i1Pro 3",
                           "X-Rite i1 Pro 3") == []


def test_m3_another_instrument_is_still_flagged():
    w = _scope_warnings("GretagMacbeth i1 Pro", "GretagMacbeth i1 Pro",
                        "X-Rite ColorMunki")
    assert len(w) == 1 and w[0]["dominant"] == "GretagMacbeth i1 Pro"
    assert [r["instrument"] for r in w[0]["runs"]] == ["X-Rite ColorMunki"]
