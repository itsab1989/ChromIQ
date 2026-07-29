"""#130 (Knut, 2026-07-29, testing the Demo-Verify-History project).

He restored a verification's used chart, got *"this chart was made without
layout information ChromIQ needs to redraw…"*, and made two points:

1. **The window says nothing about reproducing a shuffled chart.** *"This
   information does not mention that, if randomisation was used on the original
   chart, it is likely not possible to reproduce the exact chart used for
   measurement unless user has the exact random seed number… This should be
   mentioned."*
2. **The number in the file looks like a seed and is not one.** *"The ti2 in
   this case uses a tag CHART_ID "1916078606" which looks like the random seed
   number, but using it in the ChromIQ layout engine does not reproduce the
   chart correctly."*

He is right about (2), and the reason is worth stating exactly, because it is
not the reason it looks like:

* ``CHART_ID`` is what ChromIQ's layout engine writes when the chart was **not**
  shuffled (``RANDOM_START`` when it was). It still records the layout seed —
  but with no shuffle to drive, ``location_permutation`` is the identity, so the
  seed changes nothing whatsoever.
* And on a chart that *was* shuffled the seed is still not enough: the shuffle
  is applied to a patch set ArgyllCMS generated at the time, at the sizes then
  in force, and that is exactly what "no layout information" means is gone.

So one correction goes into the window with his addition: the number is **not**
missing from the chart folder — it is in the .ti2 — it is merely insufficient.
Sending a user to hunt for a seed they already have would be the wrong advice.

Finally, the state he hit was **demo data, not ChromIQ**: the demo builder
copied only the .ti2 into each dated ``chart/`` folder, while the real
:func:`snapshot_chart` copies every non-image file, the ``.channels.json``
included. The builder now calls the real function.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import workflow.verify_chart_snapshot as vcs               # noqa: E402

_TI2_HEAD = ('CTI2\nDESCRIPTOR "chart"\nORIGINATOR "ChromIQ layout engine"\n'
             'TARGET_INSTRUMENT "X-Rite ColorMunki"\nCOLOR_REP "iRGB"\n')


def _ti2(tmp_path, keyword=None, number="1916078606", name="c-verify.ti2"):
    text = _TI2_HEAD
    if keyword:
        text += f'{keyword} "{number}"\n'
    text += "\nNUMBER_OF_SETS 4\n"
    p = tmp_path / name
    p.write_text(text)
    return p


# ---- reading the chart's own answer -------------------------------------
def test_a_shuffled_chart_is_recognised(tmp_path):
    order, number = vcs.chart_order_of([_ti2(tmp_path, "RANDOM_START")])
    assert order == vcs.ORDER_SHUFFLED
    assert number == "1916078606"


def test_his_chart_is_recognised_as_not_shuffled(tmp_path):
    """His exact keyword and number."""
    order, number = vcs.chart_order_of([_ti2(tmp_path, "CHART_ID")])
    assert order == vcs.ORDER_FIXED
    assert number == "1916078606"


def test_a_chart_with_neither_keyword_says_it_does_not_know(tmp_path):
    order, number = vcs.chart_order_of([_ti2(tmp_path, None)])
    assert order == vcs.ORDER_UNKNOWN and number == ""


def test_files_without_a_ti2_say_nothing(tmp_path):
    other = tmp_path / "c-verify.ti1"
    other.write_text("CTI1\n")
    assert vcs.chart_order_of([other]) == (vcs.ORDER_UNKNOWN, "")


def test_an_unreadable_chart_never_raises(tmp_path):
    """A restore window must open whatever the file turns out to be."""
    missing = tmp_path / "gone.ti2"
    assert vcs.chart_order_of([missing]) == (vcs.ORDER_UNKNOWN, "")


def test_it_reads_the_first_ti2_only(tmp_path):
    a = _ti2(tmp_path, "RANDOM_START", "11", name="a.ti2")
    b = _ti2(tmp_path, "CHART_ID", "22", name="b.ti2")
    assert vcs.chart_order_of([a, b])[1] == "11"
    assert vcs.chart_order_of([b, a])[1] == "22"


# ---- what the window says ------------------------------------------------
def test_a_shuffled_chart_is_told_it_cannot_be_reproduced():
    """Knut's request, in the branch it was requested for."""
    msg = vcs.regeneration_message(vcs.ORDER_SHUFFLED, "1916078606")
    assert "SHUFFLED" in msg
    assert "RANDOM_START" in msg and "1916078606" in msg
    assert "not enough" in msg


def test_the_number_is_never_described_as_lost():
    """It is in the restored .ti2. Telling the user to go and find it would
    send them hunting for something they already have."""
    msg = vcs.regeneration_message(vcs.ORDER_SHUFFLED, "1916078606")
    assert "you have not lost it" in msg


def test_an_unshuffled_chart_is_told_the_number_does_nothing():
    """His case. The seed is inert on a chart that was never shuffled, so
    "use the seed" would be advice that cannot work."""
    msg = vcs.regeneration_message(vcs.ORDER_FIXED, "1916078606")
    assert "NOT shuffled" in msg
    assert "CHART_ID" in msg and "1916078606" in msg
    assert "changes nothing" in msg


def test_an_unknown_chart_still_warns_about_shuffling():
    """Not knowing is not a reason to say nothing — the warning matters most
    when we cannot check."""
    msg = vcs.regeneration_message()
    assert "shuffled" in msg and "cannot be reproduced" in msg


@pytest.mark.parametrize("order", [vcs.ORDER_SHUFFLED, vcs.ORDER_FIXED,
                                   vcs.ORDER_UNKNOWN])
def test_every_branch_reassures_about_the_measurement(order):
    """The point that stops this being frightening: the readings are fine."""
    msg = vcs.regeneration_message(order, "5")
    assert "Your measurements are safe" in msg
    assert "changes nothing about the measurement you already have" in msg
    assert "Create Chart" in msg


@pytest.mark.parametrize("order", [vcs.ORDER_SHUFFLED, vcs.ORDER_FIXED])
def test_a_missing_number_never_prints_an_empty_quote(order):
    msg = vcs.regeneration_message(order, "")
    assert '“”' not in msg
    assert "not recorded" in msg


# ---- the result carries it, and only when it is needed -------------------
def test_the_result_exposes_the_message():
    r = vcs.RestoreResult(chart_order=vcs.ORDER_SHUFFLED, chart_number="7")
    assert "RANDOM_START" in r.regeneration_message


def test_the_order_is_read_only_when_the_pages_cannot_be_rebuilt():
    """A restore that succeeded fully must not pay for a file read it will
    never use."""
    for fn in (vcs.restore_chart, vcs.restore_slot):
        src = inspect.getsource(fn)
        assert "if result.needs_regeneration:" in src, fn.__name__
        i = src.index("if result.needs_regeneration:")
        assert "chart_order_of(result.restored)" in src[i:], fn.__name__


def test_a_fresh_result_claims_nothing():
    r = vcs.RestoreResult()
    assert r.chart_order == vcs.ORDER_UNKNOWN and r.chart_number == ""


# ---- the window uses it --------------------------------------------------
def test_the_restore_window_shows_the_new_message():
    from ui.measurement_target_bar import MeasurementTargetBar
    src = inspect.getsource(MeasurementTargetBar._on_restore_clicked)
    assert "result.regeneration_message" in src
    assert "fit_message_box_buttons(box)" in src, \
        "the universal button rule applies to this window too"
    assert "without the layout information" not in src, \
        "the wording is duplicated in the UI again"


# ---- the demo data is made the way the app makes it ----------------------
def test_the_demo_builder_snapshots_with_the_real_function():
    """His session found a state ChromIQ never produces, because the builder
    wrote its own idea of a snapshot."""
    import pathlib
    src = pathlib.Path("scripts/make_demo_projects.py").read_text()
    i = src.index("def _verification(")
    body = src[i:src.index("\ndef ", i + 10)]
    assert "snapshot_chart(" in body
    assert 'chart" / f"{stem}-verify.ti2"' not in body, \
        "the builder is copying its own selection of files again"


def test_a_real_snapshot_carries_the_recipe(tmp_path):
    """Why the fix matters: with the recipe present the pages are rebuilt and
    the window Knut saw never appears."""
    from core.file_manager import Run
    run_dir = tmp_path / "P" / "runs" / "run1"
    vdir = run_dir / "verifications"
    vdir.mkdir(parents=True)
    _ti2(vdir, "CHART_ID")
    (vdir / "c-verify.channels.json").write_text('{"layout": {}}')
    (vdir / "c-verify_01.tif").write_bytes(b"II*\0")

    run = Run.for_dir(run_dir)
    verification = run.verification("2026-01-12_110000")
    verification.dir.mkdir(parents=True, exist_ok=True)
    vcs.snapshot_chart(verification)

    names = sorted(p.name for p in vcs.snapshot_files(verification))
    assert "c-verify.channels.json" in names, \
        "without this the restore cannot redraw the pages"
    result = vcs.restore_chart(verification)
    assert result.ok and not result.needs_regeneration
