"""Generated pages and retained measurements, using invented data only."""
from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest
import fitz
from tests.test_fd9_chart_creation import ti1
from tests.test_fd9_partial import setup
from tests.test_fd9_normal_measurement import tab
from tests.test_fd9_factory_workflow import native_settings
from tests.test_fd9_row_workflow import fixture_rows
from workflow.fd9.chart import build_chart, capacity
from workflow.fd9.measurement import (checked_chart, first_table, measure_chart,
                                     publish_measurement, resume_plan)
from workflow.fd9.independent import CaptureFailed


def make_chart(tmp_path, count=12):
    source, _ = ti1(tmp_path, rep="RGB", tokens=("R", "G", "B"), count=count)
    return build_chart(source, tmp_path/'multi', paper='137x170', dpi=72,
                       patch_mm=30, patch_height_mm=30, export_pdf=True,
                       randomize=False)


def test_pages_share_one_ti2_and_use_normal_print_artifacts(tmp_path):
    result = make_chart(tmp_path)
    _, layout, locations = checked_chart(result.ti2_path)
    from workflow.fd9.chart import chart_pages
    pages = chart_pages(layout)
    assert len(pages) == len(result.tiff_paths) == result.layout.pages == 2
    assert [p.name for p in result.tiff_paths] == ['multi_01.tif','multi_02.tif']
    assert len(locations) == 12  # last sheet only pads a complete column
    assert len(set(locations.values())) == 12
    assert len(pages[0]['rows'][0]) == 3 and len(pages[1]['rows'][0]) == 1
    with fitz.open(result.pdf_path) as pdf:
        assert len(pdf) == 2
    text, _, records = first_table(result.ti2_path)
    assert 'PASSES_IN_STRIPS2 "3,1"' in text
    assert [int(r['SAMPLE_ID']) for r in records] == list(range(1,13))
    side = json.loads(result.ti2_path.with_suffix('.strips.json').read_text(encoding="utf-8"))
    assert {p['page'] for p in side['patches']} == {0,1}
    assert {p['loc'] for p in side['patches']} == set(locations.values())


def capture_pages(s, *, stop_page=None, fail_page=None):
    calls = []
    def capture(source, definition, output, host, **kw):
        page = json.loads(definition.read_text(encoding="utf-8"))
        page_number = int(output.parent.name.split('-')[-1])
        calls.append((page_number, kw['row_indices']))
        if page_number == fail_page:
            raise CaptureFailed(output, 'invented connection failure', cause=ConnectionError())
        local = SimpleNamespace(**(s.__dict__ | {'layout': page}))
        rows = kw['row_indices']
        count = len(page['rows'][0])*(1 if page_number == stop_page else len(rows))
        complete = page_number != stop_page
        root = fixture_rows(local, output, rows, count, complete)
        kw['on_scan'](root)
        kw['on_readings'](count)
        if not complete:
            raise CaptureFailed(root, 'invented partial stop')
        return root
    return capture, calls


def test_full_chart_and_second_page_resume_keep_the_original_readings(setup):
    s=setup
    result=make_chart(s.tmp)
    s.chart=result.ti2_path
    settings=native_settings(s)
    capture,calls=capture_pages(s, stop_page=2)
    pages=[]; counts=[]; scans=[]
    partial=measure_chart(s.chart,settings,s.tmp/'first-pages',capture=capture,
                         on_page=lambda p,n:pages.append((p,n)),
                         on_readings=counts.append,on_scan=scans.append)
    assert not partial['complete'] and partial['patches']==10
    assert pages==[(1,2),(2,2)] and counts==[9,10]
    assert scans[-1]['page']==1 and scans[-1]['session']==str((s.tmp/'first-pages').resolve())
    original=first_table(partial['staged'])[2]
    publish_measurement(partial['staged'],partial['destination'],s.chart,allow_partial=True)
    capture,calls=capture_pages(s)
    final=measure_chart(s.chart,replace(settings,resume=True),s.tmp/'resumed-pages',capture=capture)
    assert calls==[(2,[1,2])]  # page 1 was not read again
    assert final['complete'] and final['new_readings']==2 and final['patches']==12
    assert first_table(final['staged'])[2][:10]==original


def test_connection_failure_after_page_one_keeps_a_resumable_prefix(setup):
    s=setup; s.chart=make_chart(s.tmp).ti2_path
    capture,_=capture_pages(s,fail_page=2)
    result=measure_chart(s.chart,native_settings(s),s.tmp/'failure-pages',capture=capture)
    assert result['patches']==9 and not result['complete'] and result['acquisition_error']
    publish_measurement(result['staged'],result['destination'],s.chart,allow_partial=True)
    assert len(resume_plan(s.chart,replace(native_settings(s),resume=True))[1])==9


def test_shared_gap_controls_change_each_axis_independently(tmp_path):
    from workflow.layout_engine.chart import build_chart as normal_build
    from workflow.layout_engine.presets import LayoutRecipe
    source,_=ti1(tmp_path,rep='RGB',tokens=('R','G','B'),count=40)
    r=LayoutRecipe(instrument='FD9',patch_w_mm=8,patch_h_mm=6,
                   fd9_gap_mm=None,inter_patch_mm=0,strip_gap_mm=2)
    result=normal_build(source,tmp_path/'gaps',**r.build_kwargs())
    _,layout,_=checked_chart(result.ti2_path)
    assert layout['gap_mm']==[2,0]
    assert layout['rows'][0][1]['centre_mm'][0]-layout['rows'][0][0]['centre_mm'][0]==10
    assert layout['rows'][1][0]['centre_mm'][1]-layout['rows'][0][0]['centre_mm'][1]==pytest.approx(6,abs=.02)


def test_multipage_preview_keeps_both_pages_and_global_progress(tab, setup):
    from tests.test_fd9_partial import configure
    s=setup
    s.chart=make_chart(s.tmp).ti2_path
    configure(tab,s)
    assert tab._preview.page_count()==2
    assert len(tab._patch_boxes)==2
    capture,_=capture_pages(s)
    events=[]
    result=measure_chart(s.chart,native_settings(s),s.tmp/'preview-pages',capture=capture,on_scan=events.append)
    tab._fd9_job=SimpleNamespace(session=s.tmp/'preview-pages')
    tab._fd9_live=True
    tab._reset_progress(from_files=False)
    for event in events:
        tab._fd9_scan_ready(event)
    assert tab._preview.page_count()==2 and tab._preview.current_page()==1
    assert len(tab._patch_boxes[0])==9 and len(tab._patch_boxes[1])==3
    tab._fd9_count_changed(12)
    assert tab._preview.measurement_progress()==100
    tab._preview.show_page(0)
    assert tab._preview._scan_grid[1]=={0,1,2}
    tab._fd9_live=False


def test_page_notice_reuses_the_existing_panel_without_a_continue_step(tab, setup):
    tab._fd9_live=True
    tab._fd9_page_requested(2,3)
    assert tab._page_pause['plan']['kind']=='fd9'
    assert tab._page_pause_panel.isHidden() is False
    assert tab._page_pause_continue_btn.isHidden()
    assert tab._page_pause_reread_btn.isHidden()
    tab._page_pause_continue()
    assert tab._page_pause is not None  # no chartread action or paper motion
    tab._fd9_close_page_notice()
    assert tab._page_pause is None
    tab._fd9_live=False


def test_touching_height_does_not_make_width_include_the_strip_gap(tmp_path):
    from workflow.layout_engine.instruments import geom_from_build_kwargs
    from workflow.layout_engine.geometry import compute, patch_rects_px
    geom=geom_from_build_kwargs(dict(instrument='FD9',patch_w=8,patch_h=6,
                                     inter_patch=0,strip_gap=2,dpi=300))
    layout=compute(geom,210,297,40)
    rect=patch_rects_px(geom,210,297,layout,300)[0]
    assert rect['w']*25.4/300==pytest.approx(8,abs=.09)
    assert rect['h']*25.4/300==pytest.approx(6,abs=.09)



def test_shared_six_mm_size_is_shown_as_a_number(qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from workflow.layout_engine.presets import LayoutRecipe
    panel=LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(panel)
    panel.set_recipe(LayoutRecipe(instrument='FD9',patch_w_mm=8,patch_h_mm=6))
    assert 'auto' not in panel.patch_y.text().lower()
    assert panel.patch_y.value()==6 and panel.patch_y.specialValueText()==''


@pytest.mark.parametrize("paper,width,height,gap,across,levels,pages", [
    ("A4",8,8,0,2,25,1),
    ("137x170",10,10,1,1,2,2),
])
def test_calibration_keeps_pure_ink_columns_with_shared_gaps_and_pages(
        tmp_path,paper,width,height,gap,across,levels,pages):
    from tests.test_fd9_chart_creation import ramp_ti1
    from workflow.fd9.chart import chart_pages
    tokens=("C","M","Y","K","c","m","k","1k","R","G","B")
    source=ramp_ti1(tmp_path,tokens,levels)
    result=build_chart(source,tmp_path/'calibration',paper=paper,patch_mm=width,
                       patch_height_mm=height,gap_mm=gap,strip_gap_mm=across,
                       dpi=150,ramps_per_strip=True)
    _,layout,_=checked_chart(result.ti2_path)
    sheets=chart_pages(layout)
    assert len(sheets)==result.layout.pages==pages
    seen=set()
    for sheet in sheets:
        for col in range(len(sheet['rows'][0])):
            inks={i for row in sheet['rows'] for i,v in enumerate(row[col]['device_values']) if v>0}
            assert len(inks)<=1
            seen.update(inks)
    assert seen==set(range(11))
