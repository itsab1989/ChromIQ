"""§T1.3 — what replacing a chart would cost, and how it is said.

``docs/design/unified_measurement_management.md`` §4 and §4a. Two halves:

* the decision (``workflow/chart_integrity.py``) — every row of §4's table and
  §4a's validity table, with no window in sight;
* the messages (``TabChart``) — that the sentences carry the numbers, name the
  two different kinds of page loss, and never recommend a greyed-out button.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import Run                                 # noqa: E402
from workflow.chart_integrity import (Blast, assess_profiling_chart,  # noqa: E402
                                      assess_verification_chart)


# ---- a run on disk, built up one file at a time --------------------------
def _run(tmp_path, *, ti1=False, ti2=False, recipe=False, tifs=0,
         readings=0, expected=9, profile=False, verifications=0,
         verify_chart=False):
    run_dir = tmp_path / "proj" / "runs" / "run1"
    run_dir.mkdir(parents=True, exist_ok=True)
    run = Run.for_dir(run_dir)
    if ti1:
        run.chart_ti1.write_text("x")
    if ti2:
        _write_ti2(run.chart_ti2, expected)
    if recipe:
        run.chart_channels_json.write_text("{}")
    for i in range(tifs):
        (run_dir / f"{run.stem}_{i + 1:02d}.tif").write_bytes(b"x")
    if readings:
        _write_ti3(run.measurement_ti3, readings)
    if profile:
        run.profile_icc.write_bytes(b"icc")
    if verify_chart or verifications:
        run.verifications_dir.mkdir(parents=True, exist_ok=True)
        run.verify_chart_ti2.write_text("x")
    for i in range(verifications):
        v = run.verification(f"2026-0{i + 1}-01_120000")
        v.ensure_dir()
        _write_ti3(v.measurement_ti3, 4)
    return run


def _write_ti2(path, n):
    rows = "\n".join(f"P{i + 1} 100 100 100" for i in range(n))
    path.write_text(f"CGATS.17\nNUMBER_OF_SETS {n}\n"
                    f"BEGIN_DATA\n{rows}\nEND_DATA\n")


def _write_ti3(path, n):
    rows = "\n".join(f"P{i + 1} 100 100 100 50 50 50" for i in range(n))
    path.write_text(f"CTI3\nNUMBER_OF_SETS {n}\n"
                    f"BEGIN_DATA\n{rows}\nEND_DATA\n")


# ---- §4's table ----------------------------------------------------------
def test_nothing_at_all(tmp_path):
    assert not assess_profiling_chart(_run(tmp_path)).warn


def test_a_chart_with_nothing_under_it(tmp_path):
    cost = assess_profiling_chart(
        _run(tmp_path, ti1=True, ti2=True, recipe=True, tifs=2))
    assert not cost.warn, "regenerating costs a reprint the user just asked for"


def test_a_partial_measurement(tmp_path):
    cost = assess_profiling_chart(
        _run(tmp_path, ti1=True, ti2=True, recipe=True, tifs=1, readings=3))
    assert cost.warn and cost.blast is Blast.RUN
    assert cost.readings == 3 and not cost.complete


def test_a_complete_measurement(tmp_path):
    cost = assess_profiling_chart(
        _run(tmp_path, ti1=True, ti2=True, recipe=True, readings=9,
             expected=9))
    assert cost.complete and cost.readings == 9


def test_a_measurement_and_a_profile(tmp_path):
    cost = assess_profiling_chart(
        _run(tmp_path, ti1=True, ti2=True, recipe=True, readings=9,
             profile=True))
    assert cost.has_profile and cost.blast is Blast.RUN


def test_w4_a_run_that_also_has_a_verification_history(tmp_path):
    """§4's widest blast radius: a history cannot be rebuilt at all."""
    cost = assess_profiling_chart(
        _run(tmp_path, ti1=True, ti2=True, recipe=True, readings=9,
             profile=True, verifications=3))
    assert cost.blast is Blast.RUN_AND_HISTORY
    assert cost.verifications == 3


def test_a_verification_chart_with_no_measurements_is_just_a_chart(tmp_path):
    run = _run(tmp_path, ti1=True, ti2=True, verify_chart=True)
    assert not assess_verification_chart(run).warn


def test_w5_replacing_the_verification_chart(tmp_path):
    run = _run(tmp_path, ti1=True, ti2=True, verifications=2)
    cost = assess_verification_chart(run)
    assert cost.warn and cost.blast is Blast.VERIFY_HISTORY
    assert cost.verifications == 2


def test_no_run_at_all(tmp_path):
    assert not assess_profiling_chart(None).warn
    assert not assess_verification_chart(None).warn


# ---- §4a: when is there a chart to lose ---------------------------------
def test_row2_a_patch_list_with_nothing_measured(tmp_path):
    """A patch list has never been laid out, so nothing could have measured
    it — and with no measurement in the run there is nothing to lose."""
    assert not assess_profiling_chart(_run(tmp_path, ti1=True)).warn


def test_row7_images_with_nothing_measured(tmp_path):
    assert not assess_profiling_chart(_run(tmp_path, tifs=3)).warn


def test_a_measurement_is_protected_even_where_the_chart_is_incomplete(tmp_path):
    """The correction Knut's beta74 tests forced, and they were right: the loss
    this warning is about is the MEASUREMENT. A run can hold one while its
    chart files are incomplete — going quiet there is exactly the #131
    complaint, where a measurement was archived without a word."""
    for kw in ({"ti1": True}, {"tifs": 2}, {}):
        cost = assess_profiling_chart(
            _run(tmp_path / f"c{len(kw)}{list(kw)}", readings=3, **kw))
        assert cost.warn, kw
        assert cost.readings == 3


def test_a_measurement_file_that_cannot_be_read_still_warns(tmp_path):
    """§3a's empty and unreadable states. The file is there, the archive would
    move it, so the user hears about it — with no invented number."""
    run = _run(tmp_path, ti1=True, ti2=True, recipe=True, tifs=1)
    run.measurement_ti3.write_text("not a CGATS file at all")
    cost = assess_profiling_chart(run)
    assert cost.warn and cost.has_measurement and cost.readings == 0


def test_a_profile_alone_still_warns(tmp_path):
    assert assess_profiling_chart(_run(tmp_path, profile=True)).warn


def test_row3_a_chart_that_cannot_be_redrawn(tmp_path):
    cost = assess_profiling_chart(
        _run(tmp_path, ti1=True, ti2=True, readings=3))
    assert cost.warn and not cost.can_redraw_pages
    assert cost.pages == 0
    assert not cost.pages_are_the_only_copy, "no pages, so none can be lost"


def test_row5_pages_that_cannot_be_redrawn_are_the_only_copy(tmp_path):
    cost = assess_profiling_chart(
        _run(tmp_path, ti1=True, ti2=True, tifs=2, readings=3))
    assert cost.pages == 2 and not cost.can_redraw_pages
    assert cost.pages_are_the_only_copy


def test_row6_the_ordinary_case(tmp_path):
    cost = assess_profiling_chart(
        _run(tmp_path, ti1=True, ti2=True, recipe=True, tifs=2, readings=3))
    assert cost.can_redraw_pages and not cost.pages_are_the_only_copy


def test_row8_dot_files_are_the_operating_systems_not_the_charts(tmp_path):
    """macOS drops .DS_Store into any folder opened in Finder; it must not make
    an empty run look like one holding work."""
    run = _run(tmp_path)
    (run.dir / ".DS_Store").write_bytes(b"x")
    assert not assess_profiling_chart(run).warn


# ---- Duplicate ----------------------------------------------------------
def test_duplicate_is_offered_when_the_run_has_all_four(tmp_path):
    cost = assess_profiling_chart(
        _run(tmp_path, ti1=True, ti2=True, recipe=True, tifs=1, readings=3))
    assert cost.can_duplicate


def test_duplicate_is_not_offered_for_a_chart_that_cannot_be_copied(tmp_path):
    """§4a: this feature warns from row 3 up, Duplicate needs row 6 — so a
    warning can perfectly well appear on a run that cannot be duplicated."""
    cost = assess_profiling_chart(
        _run(tmp_path, ti1=True, ti2=True, readings=3))
    assert not cost.can_duplicate
    assert "the chart's layout recipe (.channels.json)" in cost.duplicate_blocked_by
    assert "at least one printed page (.tif)" in cost.duplicate_blocked_by


# ---- it never blocks the work -------------------------------------------
def test_an_unreadable_run_does_not_stop_a_chart_being_made():
    class _Broken:
        dir = None
        def __getattr__(self, name):
            raise OSError("gone")

    assert not assess_profiling_chart(_Broken()).warn
    assert not assess_verification_chart(_Broken()).warn


# ---- the messages -------------------------------------------------------
from ui.tabs.tab_chart import TabChart            # noqa: E402


class _Talker:
    """Just enough of the tab to build message text."""
    _duplicate_blocked_note = TabChart._duplicate_blocked_note
    _pages_paragraph = TabChart._pages_paragraph
    _profiling_chart_message = TabChart._profiling_chart_message
    _verify_chart_message = TabChart._verify_chart_message


def _profiling_text(run, cost):
    title, body = _Talker()._profiling_chart_message(run, cost)
    return title + "\n\n" + body


def test_the_message_says_how_many_readings(tmp_path):
    run = _run(tmp_path, ti1=True, ti2=True, recipe=True, tifs=1, readings=3)
    text = _profiling_text(run, assess_profiling_chart(run))
    assert "a measurement of 3 patches" in text


def test_one_patch_reads_as_one_patch(tmp_path):
    """Knut, 2026-08-03: *"use house rule with real singular and plural."*"""
    run = _run(tmp_path, ti1=True, ti2=True, recipe=True, tifs=1, readings=1)
    text = _profiling_text(run, assess_profiling_chart(run))
    assert "a measurement of one patch" in text
    assert "1 patches" not in text and "(s)" not in text


def test_a_finished_measurement_is_listed_like_any_other(tmp_path):
    run = _run(tmp_path, ti1=True, ti2=True, recipe=True, tifs=1, readings=9,
               expected=9)
    text = _profiling_text(run, assess_profiling_chart(run))
    assert "a measurement of 9 patches" in text


def test_the_profile_is_named_when_there_is_one(tmp_path):
    run = _run(tmp_path, ti1=True, ti2=True, recipe=True, tifs=1, readings=9,
               profile=True)
    text = _profiling_text(run, assess_profiling_chart(run))
    assert "the profile built from it" in text


def test_w4_gets_its_own_headline_and_names_the_history(tmp_path):
    run = _run(tmp_path, ti1=True, ti2=True, recipe=True, tifs=1, readings=9,
               profile=True, verifications=3)
    title, body = _Talker()._profiling_chart_message(
        run, assess_profiling_chart(run))
    assert title == "This would undo the whole run, not just its chart"
    assert "3 dated verification runs" in body
    assert "verification history could not be continued" in body


def test_w4_names_the_three_links_of_the_chain(tmp_path):
    """§M's M-CHART-W4: measurement, profile, verification history — and one
    verification reads as one, not as "1 dated verification runs"."""
    run = _run(tmp_path, ti1=True, ti2=True, recipe=True, tifs=1, readings=9,
               profile=True, verifications=1)
    _t, body = _Talker()._profiling_chart_message(
        run, assess_profiling_chart(run))
    assert "no longer describes the chart in this run" in body
    assert "no longer describes anything on disk" in body
    assert "the one dated verification run under this run was printed" in body
    assert "it stops describing a profile that exists" in body
    assert "(s)" not in body


def test_w4_in_the_plural(tmp_path):
    run = _run(tmp_path, ti1=True, ti2=True, recipe=True, tifs=1, readings=9,
               profile=True, verifications=3)
    _t, body = _Talker()._profiling_chart_message(
        run, assess_profiling_chart(run))
    assert "the 3 dated verification runs" in body
    assert "they stop describing a profile that exists" in body


def test_one_page_image_reads_as_one(tmp_path):
    run = _run(tmp_path, ti1=True, ti2=True, tifs=1, readings=3)
    text = _profiling_text(run, assess_profiling_chart(run))
    assert "The one page image in this run is the only one there will be." in text
    assert "1 page images" not in text


def test_pages_that_cannot_be_redrawn_are_called_out(tmp_path):
    run = _run(tmp_path, ti1=True, ti2=True, tifs=2, readings=3)
    text = _profiling_text(run, assess_profiling_chart(run))
    assert "no layout recipe" in text
    assert "The 2 page images in this run are the only ones there will be." in text
    assert "keep them — they are the only copy" in text
    assert "This chart's printed pages cannot be recreated" in text


def test_pages_that_can_be_redrawn_are_not_mentioned(tmp_path):
    run = _run(tmp_path, ti1=True, ti2=True, recipe=True, tifs=2, readings=3)
    text = _profiling_text(run, assess_profiling_chart(run))
    assert "no layout recipe" not in text


def test_duplicate_is_recommended_when_it_would_work(tmp_path):
    run = _run(tmp_path, ti1=True, ti2=True, recipe=True, tifs=1, readings=3)
    text = _profiling_text(run, assess_profiling_chart(run))
    assert "Duplicate the run and make the new chart in the copy" in text
    assert "Duplicate is not available" not in text


def test_duplicate_is_explained_away_when_it_would_not(tmp_path):
    """M-DUPLICATE-BLOCKED, appended to any message that recommends it."""
    run = _run(tmp_path, ti1=True, ti2=True, readings=3)
    text = _profiling_text(run, assess_profiling_chart(run))
    assert "Duplicate is not available for this run" in text
    assert "the layout recipe (.channels.json)" in text


def test_every_profiling_message_promises_the_old_folder(tmp_path):
    for kw in ({"readings": 3},
               {"readings": 9, "profile": True},
               {"readings": 9, "profile": True, "verifications": 2}):
        run = _run(tmp_path / str(len(kw)), ti1=True, ti2=True, recipe=True,
                   tifs=1, **kw)
        text = _profiling_text(run, assess_profiling_chart(run))
        assert "“old” folder" in text
        assert "nothing is deleted" in text.lower()


def test_no_placeholder_reaches_the_screen(tmp_path):
    run = _run(tmp_path, ti1=True, ti2=True, tifs=1, readings=3,
               profile=True, verifications=2)
    text = _profiling_text(run, assess_profiling_chart(run))
    assert "{" not in text and "}" not in text


# ---- W5 -----------------------------------------------------------------
def test_w5_does_not_call_the_measurements_wrong(tmp_path):
    run = _run(tmp_path, ti1=True, ti2=True, verifications=2)
    title, body = _Talker()._verify_chart_message(assess_verification_chart(run))
    assert "already made in this run used the chart" in title
    assert "does not make them wrong" in body
    assert "The 2 dated verification measurements" in body


def test_w5_explains_what_a_trend_across_the_change_costs(tmp_path):
    run = _run(tmp_path, ti1=True, ti2=True, verifications=2)
    _t, body = _Talker()._verify_chart_message(assess_verification_chart(run))
    assert "two different charts" in body
    assert "not the same measurement made twice" in body


def test_w5_says_no_measurement_is_touched(tmp_path):
    run = _run(tmp_path, ti1=True, ti2=True, verifications=2)
    _t, body = _Talker()._verify_chart_message(assess_verification_chart(run))
    assert "no measurement is touched" in body
    assert "“old” folder inside “verifications”" in body


def test_w5_points_at_duplicate_as_the_way_to_keep_both(tmp_path):
    run = _run(tmp_path, ti1=True, ti2=True, verifications=1)
    _t, body = _Talker()._verify_chart_message(assess_verification_chart(run))
    assert "Duplicate the run instead" in body
    assert "(s)" not in body


# ---- wiring -------------------------------------------------------------
def test_the_question_is_asked_from_the_one_place_that_asks_it():
    src = inspect.getsource(TabChart._confirm_displacing_results)
    assert "assess_profiling_chart" in src and "assess_verification_chart" in src


def test_a_verification_build_no_longer_passes_silently():
    """Before §4 this returned True with no word at all for a verification
    target, so W5 could never appear."""
    src = inspect.getsource(TabChart._confirm_displacing_results)
    i = src.index("_is_verification_target()")
    assert "assess_verification_chart" in src[i:i + 300]


def test_a_new_run_is_still_never_warned_about():
    """Knut: "this is not at all relevant for a new run that is being created,
    so this message should not happen"."""
    src = inspect.getsource(TabChart._confirm_displacing_results)
    i = src.index("profile_run")
    assert "return True" in src[i:i + 700]


def test_the_item_list_holds_only_what_is_present(tmp_path):
    """§M: "{items} lists only what is actually present"."""
    run = _run(tmp_path, ti1=True, ti2=True, recipe=True, tifs=1, readings=3)
    _t, body = _Talker()._profiling_chart_message(
        run, assess_profiling_chart(run))
    bullets = [l for l in body.splitlines() if l.startswith("•")]
    assert bullets == ["•  a measurement of 3 patches"]

    run2 = _run(tmp_path / "b", ti1=True, ti2=True, recipe=True, tifs=1,
                readings=9, profile=True)
    _t, body = _Talker()._profiling_chart_message(
        run2, assess_profiling_chart(run2))
    bullets = [l for l in body.splitlines() if l.startswith("•")]
    assert bullets == ["•  a measurement of 9 patches",
                       "•  the profile built from it"]


# ---- every path that lays out a chart asks first -------------------------
def test_the_preset_paths_go_through_the_same_question():
    """§4's trigger list is not just the Generate Chart button: a preset, a
    bundled patch set and an imported chart all replace the chart a
    measurement describes."""
    src = inspect.getsource(TabChart._generate_from_ti1)
    assert "_confirm_displacing_results()" in src
    assert "ask" in inspect.signature(TabChart._generate_from_ti1).parameters


def test_the_generate_button_does_not_ask_twice():
    """_on_generate asks, then delegates — the delegate must stay quiet."""
    src = inspect.getsource(TabChart._on_generate)
    calls = [l for l in src.splitlines() if "_generate_from_ti1(" in l]
    assert calls, "the button does delegate"
    joined = src[src.index("_generate_from_ti1("):]
    for line in calls:
        # every call in this method is either complete with ask=False or is the
        # opening line of a multi-line call whose ask=False follows.
        assert "ask=False" in line or line.rstrip().endswith("("), line
    assert src.count("ask=False") == len(calls)


def test_the_live_preview_never_opens_a_window():
    """A modal on every turn of a layout knob would be unusable."""
    src = inspect.getsource(TabChart._auto_regenerate_preview)
    assert "_confirm_displacing_results" not in src
    assert "ask=False" in src


def test_the_live_preview_declines_rather_than_clobbering(tmp_path):
    """It writes a new .ti2 into the run, so a run holding a measurement must
    not be re-laid-out behind the user's back."""
    src = inspect.getsource(TabChart._auto_regenerate_preview)
    assert "assess_profiling_chart" in src
    after = src[src.index("assess_profiling_chart(_run).warn"):]
    assert "return" in after
    assert after.index("return") < after.index("_generate_from_ti1"), \
        "it must return before it re-lays-out anything"


def test_the_live_preview_says_why_it_stopped():
    src = inspect.getsource(TabChart._auto_regenerate_preview)
    assert "_say_preview_is_paused()" in src


def test_the_pause_window_comes_once_per_switch_on():
    """Knut's ruling, beta.125: *"the popup window … should come once only,
    then again the next time 'auto-update preview ...' is enabled. At the same
    time it can come in the log window until 'auto-update preview ...' is
    disabled."*"""
    src = inspect.getsource(TabChart._say_preview_is_paused)
    # the log line every time…
    i_log = src.index("appendPlainText")
    i_gate = src.index("_said_auto_update_paused")
    assert i_log < i_gate, "the log line must not be behind the once-only gate"
    # …the window only once.
    assert "box.exec()" in src
    assert "return" in src[i_gate:src.index("box.exec()")]

    # …and switching the option on re-arms it.
    toggled = inspect.getsource(TabChart._on_auto_preview_toggled)
    assert "_said_auto_update_paused = False" in toggled


def test_the_pause_window_and_the_log_line_say_the_same_thing():
    """A user comparing the two must not wonder whether they differ."""
    src = inspect.getsource(TabChart._say_preview_is_paused)
    assert "_preview_paused_body()" in src
    assert src.count("_preview_paused_body()") >= 2
