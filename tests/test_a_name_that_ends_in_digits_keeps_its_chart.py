"""A project whose name ends in ``_<digits>`` keeps its exports — beta 8, B8-04.

`_on_generate_finished` recovered the chart's file stem by stripping a trailing
``_NN`` off the first page bitmap, because printtarg numbers the pages of a
multi-page chart ``<stem>_01.tif``. A **single**-page chart is written as
``<stem>.tif`` with no number at all, so a project called ``Moab_Satin_240`` —
"Moab Entrada 240" is a paper, this is an ordinary thing to type — had its own
``_240`` eaten, and every path downstream was built from ``Moab_Satin``.

Measured in the real Create Chart window before the fix (AGENT-I, 2026-09-03,
ChromIQ layout engine, one page each):

| typed name | exports/ written | left behind | meta stamp |
|---|---|---|---|
| PlainControl | 3 files | — | ok |
| Moab_Satin_240 | **none** | `Moab_Satin.channels.json` | FileNotFoundError |
| Paper_1 | **none** | `Paper.channels.json` | FileNotFoundError |
| Paper_01 | **none** | `Paper.channels.json` | FileNotFoundError |
| Canon_Pro1000_2026 | **none** | `Canon_Pro1000.channels.json` | FileNotFoundError |
| IT8_2 | **none** | `IT8.channels.json` | FileNotFoundError |
| 240 | 3 files | — | ok |

The whole user-visible symptom was three missing lines in a log full of engine
chatter, because `write_sidecars` raised on a ``.ti1`` that does not exist and
the exception went to `log.warning` — a Python logger, not the log widget the
user is reading. The non-existent ``.ti2`` was also handed to `chart_finished`,
which crosses into the Measure tab.

The fix does not guess from the name at all: `chart_stem_from_pages` asks the
disk which of the two candidate stems the chart's own tables are called.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import chart_stem_from_pages      # noqa: E402


def _chart(folder, stem, pages=1, ext=".ti2"):
    """Write a chart on disk the way printtarg does, and return its bitmaps."""
    (folder / f"{stem}{ext}").write_text("CTI2\n", encoding="utf-8")
    if pages == 1:
        tifs = [folder / f"{stem}.tif"]
    else:
        tifs = [folder / f"{stem}_{i + 1:02d}.tif" for i in range(pages)]
    for t in tifs:
        t.write_bytes(b"II*\0")
    return tifs


def test_a_single_page_chart_keeps_the_digits_the_user_typed(tmp_path):
    for name in ("Moab_Satin_240", "Paper_1", "Paper_01",
                 "Canon_Pro1000_2026", "IT8_2", "Hahnemuehle_310"):
        d = tmp_path / name
        d.mkdir()
        assert chart_stem_from_pages(_chart(d, name)) == name


def test_a_multi_page_chart_still_loses_its_page_number(tmp_path):
    d = tmp_path / "multi"
    d.mkdir()
    assert chart_stem_from_pages(_chart(d, "PlainControl", pages=3)) == "PlainControl"


def test_a_multi_page_chart_whose_name_ends_in_digits_loses_only_the_page(tmp_path):
    """The case both readings get wrong if they are applied blindly."""
    d = tmp_path / "both"
    d.mkdir()
    assert chart_stem_from_pages(_chart(d, "Moab_Satin_240", pages=4)) \
        == "Moab_Satin_240"


def test_a_ti1_or_a_cht_answers_when_there_is_no_ti2(tmp_path):
    for ext in (".ti1", ".cht"):
        d = tmp_path / f"only{ext[1:]}"
        d.mkdir()
        assert chart_stem_from_pages(_chart(d, "Moab_Satin_240", ext=ext)) \
            == "Moab_Satin_240"


def test_with_no_chart_table_at_all_it_falls_back_to_the_old_reading(tmp_path):
    """No table on disk means no evidence, and a caller in a flow that has not
    written one must be no worse off than it was."""
    d = tmp_path / "bare"
    d.mkdir()
    (d / "PlainControl_01.tif").write_bytes(b"II*\0")
    assert chart_stem_from_pages([d / "PlainControl_01.tif"]) == "PlainControl"


def test_no_pages_is_the_callers_fallback(tmp_path):
    assert chart_stem_from_pages([]) == "chart"


def test_the_generate_handler_no_longer_guesses_from_the_name():
    """The regex is gone from the handler, not merely shadowed by it."""
    import inspect

    from ui.tabs.tab_chart import TabChart

    src = inspect.getsource(TabChart._on_generate_finished)
    assert "chart_stem_from_pages" in src
    assert r'(.+?)_\d+$' not in src, \
        "the handler is guessing the stem from the file name again"


def test_the_margin_inspector_does_not_read_a_name_as_a_page_number(tmp_path):
    """The same fault, one module along: `Moab_Satin_240.tif` was page 240, the
    index fell outside the chart's pass list, and the patch width silently
    vanished from the margin report."""
    from workflow.margin_inspector import _page_index_of

    p = tmp_path / "Moab_Satin_240.tif"
    assert _page_index_of(p, 1) == 0          # a one-page chart has one page
    assert _page_index_of(tmp_path / "PlainControl_02.tif", 3) == 1
    assert _page_index_of(tmp_path / "Moab_Satin_240_02.tif", 3) == 1
